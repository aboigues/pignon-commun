# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2.5.3"]
# ///
"""Simulation Monte-Carlo du fonds commun de Pignon commun, dans le modèle de location.

Le vélo appartient à la SCIC : le fonds paie la rente d'usage aux fabricants
même quand le vélo est vacant, les pièces, les batteries, le vol et la remise
en état entre deux locataires, en plus de ce que la page de présentation chiffre.

Usage :
    uv run simulation/simulation.py            # campagne complète
    uv run simulation/simulation.py --rapide   # contrôle rapide (volumes réduits)

Les résultats sont écrits dans simulation/resultats/.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

SEGMENTS = ("leger", "intensif")

# Probabilité annuelle de remplacer la batterie selon l'âge du vélo-cargo électrique
# (environ 1 000 cycles, soit 4 à 5 ans d'usage intensif ; une batterie par vie en moyenne).
ALEA_BATTERIE = np.array([0.0, 0.0, 0.0, 0.10, 0.25, 0.30, 0.25, 0.15])

# Tarif affiché sur la page (bloc « Construire la cotisation ») : part fixe + part au km.
TARIF_PAGE = {"leger": (120.0, (431 - 120) / 2800), "intensif": (120.0, (765 - 120) / 5500)}

BASE: dict = {
    # Parc et acteurs
    "n_leger": 1200, "n_intensif": 800, "n_fabricants": 8, "n_ateliers": 40, "horizon": 10,
    # Usage
    "km_leger": 2800.0, "km_intensif": 5500.0, "km_cv": 0.35, "km_systemique": 0.05,
    "churn": 0.20, "remplissage": 0.75, "impayes": 0.02,
    "fraude_part": 0.05, "fraude_sous_declaration": 0.30,
    # Vélos et rente d'usage
    "cout_leger": 440.0, "cout_intensif": 1170.0, "vie_leger": 10, "vie_intensif": 8,
    "taux_financement": 0.0,
    # Réparation
    "h_1000km_leger": 3.3 / 2.8, "h_1000km_intensif": 6.4 / 5.5, "h_facteur": 1.0,
    "taux_horaire": 47.0, "vieillissement": 0.04, "mo_alea": 0.10,
    "forfait_suivi": 120.0, "forfait_vacant": 0.3,
    "score_moyen": 75.0, "score_alea": 6.0, "prime_rep": 0.25, "prime_fab": 0.16,
    "pieces_km_leger": 0.025, "pieces_km_intensif": 0.045, "pieces_facteur": 1.0,
    "surcout_pieces_orphelines": 0.40, "reforme_orphelins": 0.05,
    "batterie_cout": 650.0, "batterie_facteur": 1.0,
    # Sinistralité
    "casse_leger": 0.015, "casse_intensif": 0.03, "casse_cout": 400.0, "casse_facteur": 1.0,
    "serie_proba": 0.03, "serie_part": 0.30, "serie_cout": 350.0,
    "faillite_fab": 0.04,
    "vol_leger": 0.02, "vol_intensif": 0.04, "vol_assure": True,
    "assurance_taux": 0.05, "assurance_franchise": 0.10,
    "franchise_client_leger": 150.0, "franchise_client_intensif": 300.0, "recouvrement_franchise": 0.6,
    "capteur_cout": 25.0, "capteur_renouvellement": 0.10,
    "recond_leger": 60.0, "recond_intensif": 120.0,
    # Gestion et économie générale
    "gestion_taux": 0.06, "gestion_fixe": 0.0, "inflation": 0.02, "capital_initial": 0.0,
    # Tarification
    "tarif": "location", "repricing": True, "cap_hausse": 0.10, "cap_baisse": 0.10,
    "segmentation": True, "elasticite": 1.0, "provision": 0.08,
}

# Postes « page » : pour vérifier que le modèle retrouve l'équilibre affiché sur la page.
NEUTRALISATION_PAGE = {
    "churn": 0.0, "remplissage": 1.0, "impayes": 0.0, "fraude_part": 0.0, "vieillissement": 0.0,
    "pieces_facteur": 0.0, "batterie_facteur": 0.0, "serie_proba": 0.0, "faillite_fab": 0.0,
    "vol_leger": 0.0, "vol_intensif": 0.0, "assurance_taux": 0.0, "capteur_cout": 0.0,
    "inflation": 0.0, "forfait_vacant": 0.0, "tarif": "page", "repricing": False,
}


def annuite(cout, vie, taux):
    """Rente annuelle qui rembourse le coût de fabrication sur la durée de vie, au taux donné."""
    taux = np.asarray(taux, dtype=float)
    sur = np.maximum(taux, 1e-12)
    return np.where(taux > 1e-9, cout * sur / (1 - (1 + sur) ** (-vie)), cout / vie)


def occupation_equilibre(p):
    """Part du parc louée en régime courant. « occupation_tarif », quand il est fourni dans les
    hypothèses de tarification, impose un taux plus prudent que l'équilibre."""
    if p.get("occupation_tarif") is not None:
        return p["occupation_tarif"]
    c, f = p["churn"], p["remplissage"]
    return f / (c + f - c * f)


def exposition_vol(u):
    # Un vélo vacant, stocké en atelier, est moins exposé qu'un vélo loué.
    return u + 0.3 * (1 - u)


def cout_attendu(p, s):
    """Coût annuel attendu par vélo du parc en régime stationnaire : (part liée aux km, part fixe)."""
    u = occupation_equilibre(p)
    vie = p[f"vie_{s}"]
    km_parc = u * p[f"km_{s}"]
    age_moyen = (vie - 1) / 2
    mo = (p[f"h_1000km_{s}"] * p["h_facteur"] / 1000 * km_parc * p["taux_horaire"]
          * (1 + p["vieillissement"] * age_moyen))
    pieces = p[f"pieces_km_{s}"] * p["pieces_facteur"] * km_parc
    forfait = p["forfait_suivi"] * (u + p["forfait_vacant"] * (1 - u))
    score = p["score_moyen"] / 100
    rente = annuite(p[f"cout_{s}"], vie, p["taux_financement"])
    prime_fab = p["prime_fab"] * rente * p["score_moyen"] / 75
    casse = p[f"casse_{s}"] * p["casse_facteur"] * u * p["casse_cout"]
    batterie = 0.0 if s == "leger" else ALEA_BATTERIE.sum() / vie * p["batterie_facteur"] * p["batterie_cout"]
    theta = p[f"vol_{s}"] * exposition_vol(u)
    if p["vol_assure"]:
        vol = (p["assurance_taux"] * p[f"cout_{s}"] + theta * p["assurance_franchise"] * p[f"cout_{s}"]
               - p[f"vol_{s}"] * u * p[f"franchise_client_{s}"] * p["recouvrement_franchise"])
    else:
        vol = (theta * p[f"cout_{s}"] * age_moyen / vie
               - p[f"vol_{s}"] * u * p[f"franchise_client_{s}"] * p["recouvrement_franchise"])
    capteur = p["capteur_cout"] * (1 / vie + p["capteur_renouvellement"]) if s == "leger" else 0.0
    recond = p["churn"] * u * p[f"recond_{s}"]
    part_km = mo + pieces + p["prime_rep"] * mo * score
    part_fixe = forfait + p["prime_rep"] * forfait * score + rente + prime_fab + casse + batterie + vol + capteur + recond
    return part_km, part_fixe


def tarif_location(p):
    """Tarif (part fixe €/an, part variable €/km) qui couvre le coût attendu + gestion + provision."""
    u = occupation_equilibre(p)
    n_total = p["n_leger"] + p["n_intensif"]
    charge = 1 + p["gestion_taux"] + p["provision"]
    fraude = 1 - p["fraude_part"] * p["fraude_sous_declaration"]
    tarif = {}
    for s in SEGMENTS:
        part_km, part_fixe = cout_attendu(p, s)
        part_fixe = part_fixe + p["gestion_fixe"] / n_total
        base = u * (1 - p["impayes"])
        var = part_km * charge / (base * p[f"km_{s}"] * fraude)
        fixe = part_fixe * charge / base
        tarif[s] = (float(fixe), float(var))
    return tarif


def facture_annuelle(tarif, p, s):
    fixe, var = tarif[s]
    return fixe + var * p[f"km_{s}"]


def _col(x):
    x = np.asarray(x, dtype=float)
    return x[:, None] if x.ndim == 1 else x


def simuler(p, n_traj, rng, hyp_tarif=None, mult=1.0, ref_marche=None):
    """Simule n_traj trajectoires du fonds sur l'horizon. Les paramètres peuvent être des scalaires
    ou des tableaux de taille n_traj (un jeu de paramètres par trajectoire).

    hyp_tarif : hypothèses avec lesquelles la SCIC fixe son tarif de départ.
    ref_marche : hypothèses qui définissent le prix que les usagers jugent acceptable ; au-delà,
    ils partent plus vite et se réabonnent moins (élasticité).
    """
    N, T, F = n_traj, int(p["horizon"]), int(p["n_fabricants"])
    hyp_tarif = hyp_tarif or p
    ref_marche = ref_marche or hyp_tarif
    if p["tarif"] == "page":
        tarif0 = dict(TARIF_PAGE)
    else:
        tarif0 = tarif_location(hyp_tarif)
    juste = tarif_location({**ref_marche, "tarif": "location"})
    if not p["segmentation"]:
        u = occupation_equilibre(hyp_tarif)
        poids = {s: p[f"n_{s}"] * u for s in SEGMENTS}
        km_poids = {s: poids[s] * p[f"km_{s}"] for s in SEGMENTS}
        fixe = sum(poids[s] * tarif0[s][0] for s in SEGMENTS) / sum(poids.values())
        var = sum(km_poids[s] * tarif0[s][1] for s in SEGMENTS) / sum(km_poids.values())
        tarif0 = {s: (fixe, var) for s in SEGMENTS}

    fixe = {s: np.full(N, tarif0[s][0] * mult) for s in SEGMENTS}
    var = {s: np.full(N, tarif0[s][1] * mult) for s in SEGMENTS}
    n = {s: int(p[f"n_{s}"]) for s in SEGMENTS}
    vie = {s: int(p[f"vie_{s}"]) for s in SEGMENTS}
    u0 = occupation_equilibre(p)
    cohortes = {s: np.zeros((N, vie[s]), dtype=np.int64) for s in SEGMENTS}
    occ = {}
    for s in SEGMENTS:
        cohortes[s][:, 0] = n[s]
        occ[s] = rng.binomial(n[s], np.clip(np.broadcast_to(u0, (N,)), 0, 1))
    vivant = np.ones((N, F), dtype=bool)
    reserve = np.broadcast_to(np.asarray(p["capital_initial"], float), (N,)).copy()
    rente = {s: annuite(p[f"cout_{s}"], vie[s], p["taux_financement"]) for s in SEGMENTS}

    hist = {k: np.zeros((N, T)) for k in ("reserve", "resultat", "recettes", "couts", "occupation",
                                           "facture_leger", "facture_intensif", "reparateurs", "fabricants")}
    for t in range(T):
        infl = (1 + np.asarray(p["inflation"], float)) ** t
        vivant &= rng.random((N, F)) >= _col(p["faillite_fab"])
        part_morte = 1 - vivant.mean(axis=1)
        score = np.clip(rng.normal(p["score_moyen"], p["score_alea"], N), 0, 100)
        if t == 0:  # score forfaitaire de 50 pendant les six premiers mois
            score = 0.5 * 50 + 0.5 * score
        facteur_km = rng.normal(1, p["km_systemique"], N)
        facteur_mo = rng.lognormal(0, p["mo_alea"], N)

        recettes = np.zeros(N)
        couts = np.zeros(N)
        cout_seg, recette_seg = {}, {}
        vers_rep = np.zeros(N)
        vers_fab = np.zeros(N)
        for s in SEGMENTS:
            # Élasticité : un usager qui paie plus que son coût juste part plus vite et se réabonne moins.
            facture = fixe[s] + var[s] * p[f"km_{s}"]
            facture_juste = (juste[s][0] + juste[s][1] * p[f"km_{s}"]) * infl
            surprime = np.maximum(facture / facture_juste - 1, 0)
            churn = np.clip(p["churn"] + p["elasticite"] * surprime, 0, 0.95)
            remplissage = np.clip(p["remplissage"] * (1 - p["elasticite"] * surprime), 0, 1)
            if t > 0:
                departs = rng.binomial(occ[s], churn)
                restant = occ[s] - departs
                occ[s] = restant + rng.binomial(n[s] - restant, remplissage)
            else:
                departs = np.zeros(N, dtype=np.int64)
            o = occ[s].astype(float)
            vacant = n[s] - o

            km_moyen = p[f"km_{s}"] * facteur_km
            km_reels = o * km_moyen * (1 + p["km_cv"] / np.sqrt(np.maximum(o, 1)) * rng.standard_normal(N))
            km_reels = np.maximum(km_reels, 0)
            km_declares = km_reels * (1 - p["fraude_part"] * p["fraude_sous_declaration"])
            impayes = np.clip(p["impayes"] * rng.lognormal(0, 0.3, N), 0, 0.5)
            recette = (o * fixe[s] + var[s] * km_declares) * (1 - impayes)

            coh = cohortes[s]
            ages = np.arange(vie[s])
            age_moyen = (coh * ages).sum(axis=1) / n[s]
            mo = (p[f"h_1000km_{s}"] * p["h_facteur"] / 1000 * km_reels * p["taux_horaire"]
                  * (1 + p["vieillissement"] * age_moyen) * facteur_mo * infl)
            pieces = (p[f"pieces_km_{s}"] * p["pieces_facteur"] * km_reels * infl
                      * (1 + p["surcout_pieces_orphelines"] * part_morte))
            forfait = p["forfait_suivi"] * (o + p["forfait_vacant"] * vacant) * infl
            prime_rep = p["prime_rep"] * (forfait + mo) * score / 100
            rente_seg = rente[s] * n[s]
            prime_fab = p["prime_fab"] * rente_seg * score / 75 * (1 - part_morte)

            nb_casse = rng.poisson(np.maximum(p[f"casse_{s}"] * p["casse_facteur"] * o, 0))
            casse = nb_casse * p["casse_cout"] * infl * np.maximum(
                1 + 0.8 / np.sqrt(np.maximum(nb_casse, 1)) * rng.standard_normal(N), 0)

            batterie = np.zeros(N)
            if s == "intensif":
                alea = np.clip(ALEA_BATTERIE[None, :] * _col(p["batterie_facteur"]), 0, 1)
                batterie = rng.binomial(coh, alea).sum(axis=1) * p["batterie_cout"] * infl

            taux_vol = np.clip(_col(p[f"vol_{s}"] * exposition_vol(o / n[s])), 0, 1)
            voles = rng.binomial(coh, taux_vol)
            nb_voles = voles.sum(axis=1)
            recup = (nb_voles * (o / n[s]) * p[f"franchise_client_{s}"] * p["recouvrement_franchise"])
            if p["vol_assure"]:
                vol = (p["assurance_taux"] * p[f"cout_{s}"] * n[s]
                       + nb_voles * p["assurance_franchise"] * p[f"cout_{s}"]) * infl - recup
            else:
                # La rente restant due sur un vélo volé est soldée d'un coup ; le vélo de remplacement
                # démarre une nouvelle rente.
                restant = (voles * (vie[s] - 1 - ages)[None, :]).sum(axis=1) / vie[s]
                vol = restant * p[f"cout_{s}"] * infl - recup

            # Vélos d'un fabricant disparu : faute de pièces spécifiques, une partie est réformée avant
            # la fin de sa vie ; la rente restante reste due au liquidateur et un vélo neuf le remplace.
            reformes = rng.binomial(coh - voles, np.clip(_col(part_morte * p["reforme_orphelins"]), 0, 1))
            nb_reformes = reformes.sum(axis=1)
            reforme = (reformes * (vie[s] - 1 - ages)[None, :]).sum(axis=1) / vie[s] * p[f"cout_{s}"] * infl

            recond = departs * p[f"recond_{s}"] * infl
            retraites = coh[:, -1] - voles[:, -1] - reformes[:, -1]
            nouveaux = retraites + nb_voles + nb_reformes
            capteurs = np.zeros(N)
            if s == "leger":
                installes = n[s] if t == 0 else nouveaux
                capteurs = (installes + p["capteur_renouvellement"] * n[s]) * p["capteur_cout"] * infl

            c = forfait + mo + prime_rep + pieces + rente_seg + prime_fab + casse + batterie + vol + recond + capteurs + reforme
            cout_seg[s] = c
            recette_seg[s] = recette
            couts += c
            recettes += recette
            vers_rep += forfait + mo + prime_rep
            vers_fab += rente_seg + prime_fab
            hist[f"facture_{s}"][:, t] = fixe[s] + var[s] * p[f"km_{s}"]

            # Vieillissement du parc : les vélos en fin de vie et les vélos volés sont remplacés à neuf.
            coh -= voles + reformes
            coh[:, 1:] = coh[:, :-1].copy()
            coh[:, 0] = nouveaux

        evenements = (rng.random((N, F)) < _col(p["serie_proba"])) & ~vivant
        n_parc = sum(n.values())
        serie = evenements.sum(axis=1) * (n_parc / F) * p["serie_part"] * p["serie_cout"] * infl
        gestion = p["gestion_taux"] * (couts + serie) + p["gestion_fixe"] * infl
        couts = couts + serie + gestion
        resultat = recettes - couts
        reserve = reserve + resultat

        hist["reserve"][:, t] = reserve
        hist["resultat"][:, t] = resultat
        hist["recettes"][:, t] = recettes
        hist["couts"][:, t] = couts
        hist["occupation"][:, t] = sum(occ[s] for s in SEGMENTS) / n_parc
        hist["reparateurs"][:, t] = vers_rep
        hist["fabricants"][:, t] = vers_fab

        if p["repricing"]:
            # Révision annuelle : chaque catégorie vise son coût observé + provision, hausse et baisse plafonnées.
            partage = {s: n[s] / n_parc for s in SEGMENTS}
            if p["segmentation"]:
                for s in SEGMENTS:
                    cible = (cout_seg[s] + (serie + gestion) * partage[s]) * (1 + p["provision"])
                    m = np.clip(cible / np.maximum(recette_seg[s], 1), 1 - p["cap_baisse"], 1 + p["cap_hausse"])
                    fixe[s] *= m
                    var[s] *= m
            else:
                m = np.clip(couts * (1 + p["provision"]) / np.maximum(recettes, 1),
                            1 - p["cap_baisse"], 1 + p["cap_hausse"])
                for s in SEGMENTS:
                    fixe[s] *= m
                    var[s] *= m
    return hist


def indicateurs(hist, p):
    R = hist["reserve"]
    cumul_sans_capital = np.cumsum(hist["resultat"], axis=1)
    creux = cumul_sans_capital.min(axis=1)
    ruine = (R < 0).any(axis=1)
    premiere = np.where(ruine, (R < 0).argmax(axis=1) + 1, 0)
    res = hist["resultat"]
    marge = res.sum(axis=1) / hist["recettes"].sum(axis=1)
    n_parc = p["n_leger"] + p["n_intensif"]

    def q(x, a):
        return float(np.quantile(x, a))

    return {
        "p_ruine": float(ruine.mean()),
        "p_ruine_3ans": float((R[:, :3] < 0).any(axis=1).mean()),
        "annee_ruine_mediane": float(np.median(premiere[ruine])) if ruine.any() else None,
        "reserve_finale_p50": q(R[:, -1], 0.5),
        "reserve_finale_p05": q(R[:, -1], 0.05),
        "reserve_finale_p01": q(R[:, -1], 0.01),
        "resultat_annuel_moyen": float(res.mean()),
        "pire_annee_p01": q(res.min(axis=1), 0.01),
        "marge_moyenne": float(marge.mean()),
        "capital_requis_99": max(0.0, -q(creux, 0.01)),
        "capital_requis_par_velo": max(0.0, -q(creux, 0.01)) / n_parc,
        "occupation_moyenne": float(hist["occupation"].mean()),
        "facture_leger_mois_an1": float(hist["facture_leger"][:, 0].mean() / 12),
        "facture_intensif_mois_an1": float(hist["facture_intensif"][:, 0].mean() / 12),
        "facture_leger_mois_an10_p50": q(hist["facture_leger"][:, -1], 0.5) / 12,
        "facture_intensif_mois_an10_p50": q(hist["facture_intensif"][:, -1], 0.5) / 12,
        "facture_intensif_mois_an10_p95": q(hist["facture_intensif"][:, -1], 0.95) / 12,
        "revenu_atelier_an1": float(hist["reparateurs"][:, 0].mean() / p["n_ateliers"]),
        "flux_fabricants_an1": float(hist["fabricants"][:, 0].mean()),
        "fonds_collecte_an1": float(hist["recettes"][:, 0].mean()),
    }


def tarif_equilibre(p, n_traj, seed, hyp_tarif=None, cible=0.01, ref_marche=None):
    """Plus petit multiplicateur du tarif initial qui garde la probabilité de ruine sous la cible.

    La relation n'est pas monotone : un tarif trop haut fait partir les usagers (élasticité) et
    remplit le parc de vélos vacants qui coûtent leur rente. On balaie donc une grille, puis on affine.
    """

    def pr(m):
        h = simuler(p, n_traj, np.random.default_rng(seed), hyp_tarif, mult=m, ref_marche=ref_marche)
        return float((h["reserve"] < 0).any(axis=1).mean())

    grille = np.round(np.arange(0.80, 2.501, 0.05), 2)
    precedent = None
    for m in grille:
        if pr(m) <= cible:
            if precedent is None:
                return float(m)
            bas, haut = precedent, float(m)
            for _ in range(5):
                milieu = (bas + haut) / 2
                if pr(milieu) <= cible:
                    haut = milieu
                else:
                    bas = milieu
            return round(haut, 3)
        precedent = float(m)
    return None


# --------------------------------------------------------------------------------------------
# Scénarios nommés. « hyp » : hypothèses utilisées pour fixer le tarif (par défaut BASE, c'est-à-dire
# que la réalité s'écarte de ce qu'on avait prévu en tarifant). « hyp: 'stress' » : la SCIC connaît
# le stress à l'avance et tarife en conséquence.
# --------------------------------------------------------------------------------------------
TEMPETE_MODEREE = {"casse_facteur": 1.5, "h_facteur": 1.2, "vol_leger": 0.03, "vol_intensif": 0.06,
                   "churn": 0.30, "remplissage": 0.65, "faillite_fab": 0.08, "impayes": 0.04}
TEMPETE_SEVERE = {"casse_facteur": 2.5, "h_facteur": 1.4, "pieces_facteur": 1.5, "batterie_facteur": 1.6,
                  "vol_leger": 0.04, "vol_intensif": 0.08, "vol_assure": False, "churn": 0.40,
                  "remplissage": 0.55, "faillite_fab": 0.15, "serie_proba": 0.08, "impayes": 0.06,
                  "fraude_part": 0.25, "inflation": 0.04}

SCENARIOS = [
    ("S00", "Contrôle : la page telle quelle", "Postes de la page seulement, parc toujours loué, tarif de la page.",
     NEUTRALISATION_PAGE, {}),
    ("S01", "Location, tarif de la page", "Tous les coûts de la location, mais le tarif affiché sur la page, sans révision.",
     {"tarif": "page", "repricing": False}, {}),
    ("S02", "Location, tarif recalculé (référence)", "Tarif recalculé sur tous les coûts de la location, révision annuelle plafonnée à ±10 %.",
     {}, {}),
    ("S03", "Référence sans révision annuelle", "Même tarif de départ, jamais révisé pendant 10 ans (inflation 2 %).",
     {"repricing": False}, {}),
    ("S04", "Casse prématurée ×2", "Deux fois plus de ruptures de cadre, moteur ou batterie que prévu.",
     {"casse_facteur": 2.0}, {}),
    ("S05", "Casse prématurée ×3, coût ×2,25", "Trois fois plus de casse, à 900 € l'événement (cadre ou moteur de cargo).",
     {"casse_facteur": 3.0, "casse_cout": 900.0}, {}),
    ("S06", "Main d'œuvre +40 %", "Les heures par 1 000 km sont sous-estimées de 40 %.",
     {"h_facteur": 1.4}, {}),
    ("S07", "Pièces ×2", "Pièces d'usure deux fois plus chères ou plus consommées que prévu.",
     {"pieces_facteur": 2.0}, {}),
    ("S08", "Batteries à durée courte", "Batteries remplacées deux fois plus souvent (vélos-cargos).",
     {"batterie_facteur": 2.0}, {}),
    ("S09", "Coût de fabrication réaliste, découvert après tarification", "Vélo-cargo électrique à 2 800 € et vélo classique à 600 €, tarif calé sur 1 170 € et 440 €.",
     {"cout_intensif": 2800.0, "cout_leger": 600.0}, {}),
    ("S10", "Coût de fabrication réaliste, tarifé correctement", "Même coûts, mais connus au moment de fixer le tarif.",
     {"cout_intensif": 2800.0, "cout_leger": 600.0}, {"hyp": "stress"}),
    ("S11", "Rente financée à 5 %", "Le fabricant fait payer le coût de l'argent avancé sur 8 à 10 ans.",
     {"taux_financement": 0.05}, {}),
    ("S12", "Faillites de fabricants en chaîne", "15 % de risque de faillite par fabricant et par an : plus de garantie, pièces orphelines.",
     {"faillite_fab": 0.15}, {}),
    ("S13", "Défauts de série, faillites et vélos orphelins", "10 % de défaut de série et 10 % de faillite par fabricant et par an ; 15 % des vélos orphelins réformés chaque année.",
     {"serie_proba": 0.10, "faillite_fab": 0.10, "reforme_orphelins": 0.15}, {}),
    ("S14", "Vol élevé, assuré", "Vol à 4 % (classique) et 8 % (cargo électrique) par an, assurance à 5 % de la valeur.",
     {"vol_leger": 0.04, "vol_intensif": 0.08}, {}),
    ("S15", "Vol élevé, non assuré", "Même vol, la SCIC s'auto-assure : la rente restante du vélo volé est soldée.",
     {"vol_leger": 0.04, "vol_intensif": 0.08, "vol_assure": False}, {}),
    ("S16", "Vacance forte", "40 % des locataires partent chaque année, un vélo vacant sur deux est reloué.",
     {"churn": 0.40, "remplissage": 0.50}, {}),
    ("S17", "Fraude kilométrique massive", "30 % des usagers sous-déclarent 40 % de leurs km.",
     {"fraude_part": 0.30, "fraude_sous_declaration": 0.40}, {}),
    ("S18", "Usage réel +30 % de km", "Les vélos roulent 30 % de plus que prévu (usure et km déclarés).",
     {"km_leger": 2800 * 1.3, "km_intensif": 5500 * 1.3}, {}),
    ("S19", "Impayés à 8 %", "Défauts de paiement quatre fois plus élevés.",
     {"impayes": 0.08}, {}),
    ("S20", "Inflation 5 % sans révision", "Inflation des coûts de 5 % par an, tarif figé.",
     {"inflation": 0.05, "repricing": False}, {}),
    ("S21", "Primes au plafond", "Score moyen de 95 : les primes de durabilité coûtent plus que prévu.",
     {"score_moyen": 95.0}, {}),
    ("S22", "Coûts de gestion fixes réalistes", "180 000 €/an de structure (2 ETP, registre, comité) au lieu de 6 %.",
     {"gestion_fixe": 180000.0}, {}),
    ("S23", "Tarif unique + élasticité (spirale)", "Pas de segmentation : les usagers légers paient pour les intensifs et partent.",
     {"segmentation": False, "elasticite": 1.5}, {}),
    ("S24", "Pilote 200 vélos, 2 fabricants", "Petit pool : 120 légers, 80 cargos, 2 fabricants, 4 ateliers.",
     {"n_leger": 120, "n_intensif": 80, "n_fabricants": 2, "n_ateliers": 4}, {}),
    ("S25", "Pilote 200 vélos, 2 fabricants, faillites", "Petit pool avec 10 % de faillite annuelle par fabricant.",
     {"n_leger": 120, "n_intensif": 80, "n_fabricants": 2, "n_ateliers": 4, "faillite_fab": 0.10}, {}),
    ("S26", "Grande échelle : 20 000 vélos", "Dix fois le parc de la page, 20 fabricants, 400 ateliers.",
     {"n_leger": 12000, "n_intensif": 8000, "n_fabricants": 20, "n_ateliers": 400}, {}),
    ("S27", "Tempête modérée", "Casse ×1,5, MO +20 %, vol 3 à 6 %, vacance forte, faillites 8 %, impayés 4 %.",
     TEMPETE_MODEREE, {}),
    ("S28", "Tempête sévère", "Tout ce qui peut mal tourner en même temps, vol non assuré et inflation 4 %.",
     TEMPETE_SEVERE, {}),
    ("S29", "Tempête modérée, tarifée à l'avance", "La tempête modérée, mais connue au moment de tarifer.",
     TEMPETE_MODEREE, {"hyp": "stress"}),
    ("S30", "Coût de fabrication réaliste, usagers captifs", "Comme S10, mais les usagers (flottes pro) ne partent pas quand le prix monte.",
     {"cout_intensif": 2800.0, "cout_leger": 600.0, "elasticite": 0.0}, {"hyp": "stress"}),
    ("S31", "Tempête sévère, tarifée à l'avance, usagers captifs", "Le pire cas connu d'avance, sans départ des usagers : le prix nécessaire.",
     {**TEMPETE_SEVERE, "elasticite": 0.0}, {"hyp": "stress"}),
    ("S32", "Tarif prudent (80 % d'occupation), réalité conforme", "Tarif calculé en supposant 80 % du parc loué au lieu de 94 % ; la réalité suit les hypothèses de référence.",
     {}, {"hyp": {"occupation_tarif": 0.80}}),
    ("S33", "Tarif prudent (80 %), vacance forte", "Tarif prudent face à la vacance forte de S16.",
     {"churn": 0.40, "remplissage": 0.50}, {"hyp": {"occupation_tarif": 0.80}}),
    ("S34", "Tarif prudent (80 %), tempête modérée", "Tarif prudent face à la tempête modérée de S27.",
     TEMPETE_MODEREE, {"hyp": {"occupation_tarif": 0.80}}),
    ("S35", "Tarif prudent (80 %), pièces ×2", "Tarif prudent face aux pièces sous-estimées de S07.",
     {"pieces_facteur": 2.0}, {"hyp": {"occupation_tarif": 0.80}}),
    ("S36", "Tarif très prudent (70 %), tempête modérée", "Tarif calculé en supposant 70 % du parc loué, face à la tempête modérée.",
     TEMPETE_MODEREE, {"hyp": {"occupation_tarif": 0.70}}),
]

# Matrice « vacance prudente » : taux d'occupation retenu pour tarifer × réalité rencontrée.
OCCUPATIONS_TARIF = {"94 % (référence)": None, "88 %": 0.88, "80 %": 0.80, "70 %": 0.70}
REALITES_VACANCE = {
    "Réalité conforme": {},
    "Vacance forte (S16)": {"churn": 0.40, "remplissage": 0.50},
    "Tempête modérée (S27)": TEMPETE_MODEREE,
    "Pièces ×2 (S07)": {"pieces_facteur": 2.0},
    "Main d'œuvre +40 % (S06)": {"h_facteur": 1.4},
}


def matrice_vacance(n_traj, seed):
    lignes = []
    for elasticite in (1.0, 0.0):
        for libelle, occupation in OCCUPATIONS_TARIF.items():
            hyp = {**BASE, "occupation_tarif": occupation}
            tarif = tarif_location(hyp)
            ligne = {"elasticite": elasticite, "occupation_tarif": libelle,
                     "leger_mois": facture_annuelle(tarif, BASE, "leger") / 12,
                     "intensif_mois": facture_annuelle(tarif, BASE, "intensif") / 12, "realites": {}}
            for nom, surcharges in REALITES_VACANCE.items():
                p = {**BASE, **surcharges, "elasticite": elasticite}
                h = simuler(p, n_traj, np.random.default_rng(seed), hyp_tarif=hyp, ref_marche=BASE)
                ind = indicateurs(h, p)
                ligne["realites"][nom] = {"p_ruine": ind["p_ruine"], "occupation": ind["occupation_moyenne"],
                                          "capital_requis_99": ind["capital_requis_99"]}
            lignes.append(ligne)
    return lignes

# Plages explorées par l'analyse de sensibilité globale (tirage uniforme, hypercube latin).
# Paramètres de structure : connus au moment de tarifer, ce ne sont pas des aléas.
STRUCTURE = ("n_leger", "n_intensif", "n_fabricants", "n_ateliers", "segmentation", "elasticite",
             "vol_assure", "tarif", "repricing")

PLAGES = {
    "km_facteur": (0.7, 1.3),
    "churn": (0.10, 0.35),
    "remplissage": (0.55, 0.95),
    "impayes": (0.0, 0.06),
    "fraude_part": (0.0, 0.30),
    "cout_leger": (380.0, 650.0),
    "cout_intensif": (1000.0, 3000.0),
    "taux_financement": (0.0, 0.06),
    "taux_horaire": (40.0, 58.0),
    "h_facteur": (0.75, 1.35),
    "vieillissement": (0.0, 0.08),
    "pieces_facteur": (0.5, 1.7),
    "batterie_facteur": (0.5, 1.7),
    "casse_facteur": (0.5, 3.0),
    "serie_proba": (0.0, 0.08),
    "faillite_fab": (0.0, 0.12),
    "reforme_orphelins": (0.0, 0.15),
    "vol_leger": (0.01, 0.04),
    "vol_intensif": (0.02, 0.07),
    "inflation": (0.0, 0.04),
    "gestion_fixe": (0.0, 150000.0),
    "score_moyen": (60.0, 95.0),
}


def rangs(x):
    r = np.empty_like(x)
    r[np.argsort(x)] = np.arange(len(x))
    return r


def sensibilite(n_jeux, n_traj, seed):
    rng = np.random.default_rng(seed)
    k = len(PLAGES)
    # Hypercube latin : chaque paramètre couvre toute sa plage de façon régulière.
    u = (rng.permuted(np.tile(np.arange(n_jeux), (k, 1)), axis=1).T + rng.random((n_jeux, k))) / n_jeux
    noms = list(PLAGES)
    tirages = {nom: PLAGES[nom][0] + u[:, i] * (PLAGES[nom][1] - PLAGES[nom][0]) for i, nom in enumerate(noms)}

    p_ruine = np.zeros(n_jeux)
    marge = np.zeros(n_jeux)
    capital = np.zeros(n_jeux)
    bloc = max(1, 200_000 // n_traj)
    for debut in range(0, n_jeux, bloc):
        fin = min(n_jeux, debut + bloc)
        idx = np.repeat(np.arange(debut, fin), n_traj)
        p = dict(BASE)
        for nom in noms:
            if nom == "km_facteur":
                continue
            p[nom] = tirages[nom][idx]
        p["km_leger"] = BASE["km_leger"] * tirages["km_facteur"][idx]
        p["km_intensif"] = BASE["km_intensif"] * tirages["km_facteur"][idx]
        h = simuler(p, len(idx), rng, hyp_tarif=BASE)
        ruine = (h["reserve"] < 0).any(axis=1).reshape(fin - debut, n_traj)
        m = (h["resultat"].sum(axis=1) / h["recettes"].sum(axis=1)).reshape(fin - debut, n_traj)
        creux = np.cumsum(h["resultat"], axis=1).min(axis=1).reshape(fin - debut, n_traj)
        p_ruine[debut:fin] = ruine.mean(axis=1)
        marge[debut:fin] = m.mean(axis=1)
        capital[debut:fin] = np.maximum(0, -np.quantile(creux, 0.01, axis=1))

    r_marge = rangs(marge)
    resultats = []
    for nom in noms:
        x = tirages[nom]
        rho = float(np.corrcoef(rangs(x), r_marge)[0, 1])
        bas = x <= np.quantile(x, 0.2)
        haut = x >= np.quantile(x, 0.8)
        resultats.append({
            "parametre": nom, "plage": PLAGES[nom], "spearman_marge": rho,
            "p_ruine_quintile_bas": float(p_ruine[bas].mean()),
            "p_ruine_quintile_haut": float(p_ruine[haut].mean()),
        })
    resultats.sort(key=lambda r: -abs(r["spearman_marge"]))

    # Seuils de rupture sur les deux paramètres les plus influents : grille de probabilité de ruine.
    a, b = resultats[0]["parametre"], resultats[1]["parametre"]
    qa = np.quantile(tirages[a], [0, .25, .5, .75, 1])
    qb = np.quantile(tirages[b], [0, .25, .5, .75, 1])
    grille = []
    for i in range(4):
        ligne = []
        for j in range(4):
            sel = ((tirages[a] >= qa[i]) & (tirages[a] <= qa[i + 1]) & (tirages[b] >= qb[j]) & (tirages[b] <= qb[j + 1]))
            ligne.append(float(p_ruine[sel].mean()))
        grille.append(ligne)

    return {
        "n_jeux": n_jeux, "n_traj_par_jeu": n_traj,
        "p_ruine_globale": float(p_ruine.mean()),
        "part_jeux_ruine_sup_5pct": float((p_ruine > 0.05).mean()),
        "part_jeux_ruine_sup_50pct": float((p_ruine > 0.5).mean()),
        "marge_mediane": float(np.median(marge)),
        "capital_requis_99_median": float(np.median(capital)),
        "capital_requis_99_p90": float(np.quantile(capital, 0.9)),
        "classement": resultats,
        "grille": {"x": a, "y": b, "bornes_x": qa.tolist(), "bornes_y": qb.tolist(), "p_ruine": grille},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapide", action="store_true")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    n_traj = 2_000 if args.rapide else 20_000
    n_eq = 1_000 if args.rapide else 10_000
    n_jeux, n_traj_jeu = (300, 50) if args.rapide else (5_000, 200)

    sortie = Path(__file__).parent / "resultats"
    sortie.mkdir(exist_ok=True)
    debut = time.time()
    total_traj = 0

    tarif_ref = tarif_location(BASE)
    scenarios = []
    for code, titre, desc, surcharges, opts in SCENARIOS:
        p = {**BASE, **surcharges}
        hyp = p if opts.get("hyp") == "stress" else {**BASE, **{k: v for k, v in surcharges.items() if k in STRUCTURE}}
        if isinstance(opts.get("hyp"), dict):
            hyp = {**hyp, **opts["hyp"]}
        # Le prix jugé acceptable par les usagers reste celui des hypothèses de référence, même quand
        # la SCIC tarife sur des coûts plus élevés : le marché ne suit pas les coûts de la SCIC.
        marche = {**BASE, **{k: v for k, v in surcharges.items() if k in STRUCTURE}}
        if code == "S00":
            hyp = marche = p
        h = simuler(p, n_traj, np.random.default_rng(args.seed), hyp, ref_marche=marche)
        total_traj += n_traj
        ind = indicateurs(h, p)
        ind["tarif_equilibre_mult"] = tarif_equilibre(p, n_eq, args.seed + 1, hyp, ref_marche=marche)
        ind["facture_mois_depart"] = {s: facture_annuelle(tarif_location(hyp), p, s) / 12 for s in SEGMENTS}
        total_traj += n_eq * 40  # ordre de grandeur des évaluations de la grille
        scenarios.append({"code": code, "titre": titre, "description": desc, **ind})
        print(f"{code} {titre[:48]:48} ruine={ind['p_ruine']:.3f} marge={ind['marge_moyenne']:+.3f} "
              f"capital99={ind['capital_requis_99']:>10,.0f} eq={ind['tarif_equilibre_mult']}", flush=True)

    sens = sensibilite(n_jeux, n_traj_jeu, args.seed + 7)
    total_traj += n_jeux * n_traj_jeu
    n_mat = 1_000 if args.rapide else 10_000
    vacance = matrice_vacance(n_mat, args.seed + 3)
    total_traj += n_mat * 2 * len(OCCUPATIONS_TARIF) * len(REALITES_VACANCE)

    resultats = {
        "graine": args.seed, "trajectoires_simulees": total_traj, "horizon_ans": BASE["horizon"],
        "duree_s": round(time.time() - debut, 1),
        "tarif_reference": {s: {"fixe_an": tarif_ref[s][0], "par_km": tarif_ref[s][1],
                                "mois_moyen": facture_annuelle(tarif_ref, BASE, s) / 12} for s in SEGMENTS},
        "tarif_page": {s: {"fixe_an": TARIF_PAGE[s][0], "par_km": TARIF_PAGE[s][1],
                           "mois_moyen": facture_annuelle(TARIF_PAGE, BASE, s) / 12} for s in SEGMENTS},
        "cout_attendu_par_velo": {s: dict(zip(("part_km", "part_fixe"), map(float, cout_attendu(BASE, s))))
                                  for s in SEGMENTS},
        "occupation_equilibre": occupation_equilibre(BASE),
        "scenarios": scenarios, "sensibilite": sens, "vacance_prudente": vacance,
    }
    nom = "resultats-rapide.json" if args.rapide else "resultats.json"
    (sortie / nom).write_text(json.dumps(resultats, ensure_ascii=False, indent=1))
    print(f"\n{total_traj:,} trajectoires de {BASE['horizon']} ans en {resultats['duree_s']} s -> {sortie / nom}")


if __name__ == "__main__":
    main()
