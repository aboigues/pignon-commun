# Simulation économique du fonds commun — scénarios et cas critiques

*Dernière mise à jour : 2026-09-22*

Ce document décrit la simulation économique de Pignon commun dans le modèle de location : ses hypothèses, sa méthode, les résultats de 32 scénarios et d'une analyse de sensibilité, puis ce qu'il faut en conclure avant tout pilote. Le code se trouve dans [`simulation/simulation.py`](../simulation/simulation.py) et les résultats bruts dans `simulation/resultats/resultats.json`.

La campagne compte **14,4 millions de trajectoires** du fonds, chacune sur 10 ans. Tous les montants restent illustratifs : la simulation dit quelles hypothèses comptent et à partir de quand le modèle casse, pas ce que coûtera réellement le service.

## Ce qu'il faut retenir

1. **Le tarif de la page ne couvre pas la location.** Une fois comptés les coûts qui reviennent à la SCIC parce qu'elle est propriétaire des vélos (pièces, batteries, assurance vol, vélos vacants, remise en état entre deux locataires), le tarif de référence passe de **36 à 52 €/mois** pour un usage léger et de **64 à 114 €/mois** pour un vélo-cargo. Au tarif de la page, le fonds perd 65 % de ses recettes et il est en faillite dès la première année dans toutes les trajectoires.
2. **Avec le tarif recalculé et une révision annuelle, le fonds résiste aux sinistres.** Casse deux fois plus fréquente, vol élevé, faillites de fabricants en chaîne, défauts de série, fraude kilométrique massive, pilote de 200 vélos : la probabilité de ruine reste sous 1 %.
3. **Ce qui fait tomber le fonds, ce sont les erreurs de coût récurrentes, pas les accidents.** Pièces d'usure ×2 (81 % de ruine), main d'œuvre +40 % (54 %), vacance forte (61 %), tarif jamais révisé (65 %), coûts de structure fixes (30 %).
4. **Le paramètre le plus dangereux est le coût de fabrication du vélo-cargo.** À 2 800 € au lieu de 1 170 €, il faut facturer 148 €/mois. À ce prix, les usagers partent, le parc se vide et le fonds fait faillite dans 100 % des trajectoires, même quand le tarif est juste dès le départ. Le modèle ne tient alors qu'avec des usagers captifs, comme des flottes professionnelles.
5. **La taille du parc protège moins que prévu.** Un pilote de 200 vélos n'est pas plus fragile qu'un parc de 20 000 vélos, car les risques qui comptent (erreur de prix, inflation, main d'œuvre) touchent tout le parc en même temps et ne se mutualisent pas. C'est la révision annuelle du tarif qui protège le fonds, pas la loi des grands nombres.
6. **Le revenu des ateliers reste stable dans presque tous les scénarios**, autour de 18 000 € par atelier pour 50 vélos la première année et de 20 500 € en régime courant, puisque le socle n'a pas de malus. Le risque est porté par le fonds, donc par les usagers.

## 1. Le modèle simulé

### Ce qui change avec la location

La page chiffre une cotisation qui couvre le suivi, la main d'œuvre, les primes et la rente d'usage des fabricants, « hors pièces ». Avec la location, la SCIC est propriétaire du parc : elle paie aussi ce qu'un propriétaire paie.

| Poste | Page initiale | Location simulée |
| --- | --- | --- |
| Forfait de suivi, main d'œuvre, primes | Oui | Oui, plus le vieillissement du vélo (+4 % d'heures par année d'âge) |
| Rente d'usage fabricant | Oui, sur les vélos loués | Oui, **sur tous les vélos du parc**, loués ou vacants |
| Pièces d'usure | Non, refacturées au client | À la charge de la SCIC |
| Batterie des vélos-cargos électriques | Non | Environ un remplacement par vie, à 650 € |
| Vol | Hors fonds | Assurance du parc (5 % de la valeur par an) et franchise en partie refacturée au locataire |
| Vélos vacants entre deux locataires | Non | 6 % du parc en moyenne ; rente et forfait réduit payés quand même |
| Remise en état à la restitution | Non | 60 € (classique) et 120 € (cargo) par départ |
| Capteurs des vélos mécaniques | Non | 25 € par vélo, 10 % renouvelés chaque année |
| Impayés et fraude kilométrique | Non | 2 % d'impayés, 5 % d'usagers qui sous-déclarent 30 % de leurs km |
| Inflation | Non | 2 % par an sur les coûts |

### Décomposition du coût annuel attendu par vélo du parc

| Poste | Usage léger (vélo classique) | Usage intensif (cargo électrique) |
| --- | --- | --- |
| Forfait de suivi | 115 € | 115 € |
| Main d'œuvre | 172 € | 321 € |
| Prime de durabilité réparateur | 54 € | 82 € |
| Pièces d'usure | 66 € | 232 € |
| Rente d'usage fabricant | 44 € | 146 € |
| Prime de durabilité fabricant | 7 € | 23 € |
| Casse prématurée | 6 € | 11 € |
| Batterie | — | 85 € |
| Vol (assurance, franchise) | 21 € | 56 € |
| Capteur | 5 € | — |
| Remise en état entre deux locataires | 11 € | 23 € |
| **Coût par vélo du parc** | **500 €** | **1 095 €** |
| Tarif par vélo loué (+ gestion 6 %, provision 8 %, occupation 94 %, impayés 2 %) | **625 €/an, soit 52 €/mois** | **1 370 €/an, soit 114 €/mois** |
| Rappel du tarif initial de la page | 431 €/an, soit 36 €/mois | 765 €/an, soit 64 €/mois |

Le tarif garde la structure de la page, avec une part fixe et une part au kilomètre : 286 € par an plus 0,12 €/km pour l'usage léger, 597 € par an plus 0,14 €/km pour le vélo-cargo.

### Mécanique d'une année simulée

Chaque trajectoire suit le fonds année par année sur 10 ans :

1. **Fabricants** : chacun peut faire faillite. Ses vélos perdent alors la garantie des défauts de série, leurs pièces coûtent 40 % plus cher et 5 % d'entre eux sont réformés chaque année faute de pièces. La rente restante reste due au liquidateur.
2. **Locataires** : 20 % partent chaque année. Trois vélos vacants sur quatre retrouvent un locataire. Si le prix dépasse le prix de référence du marché, les départs augmentent et les réabonnements diminuent en proportion (élasticité de 1).
3. **Usage** : le kilométrage varie d'un vélo à l'autre (écart-type de 35 %) et d'une année à l'autre pour tout le parc (5 %). La part variable est facturée sur les km déclarés, l'usure est payée sur les km réels.
4. **Coûts** : main d'œuvre avec un aléa annuel commun à tout le parc (10 %), pièces, primes selon un score de durabilité aléatoire (75 ± 6, forfait de 50 pendant six mois), casse prématurée (loi de Poisson), batteries selon l'âge, vol par cohorte d'âge, défauts de série par fabricant.
5. **Parc** : les vélos en fin de vie, volés ou réformés sont remplacés à neuf. Un vélo volé non assuré oblige à solder d'un coup la rente qui restait due.
6. **Réserve** : recettes moins coûts. Le fonds est **ruiné** si sa réserve passe sous zéro une seule fois en 10 ans, sans capital de départ.
7. **Révision du tarif** : chaque catégorie vise son coût observé plus la provision de 8 %, avec une hausse ou une baisse plafonnée à 10 % par an.

### Indicateurs

| Indicateur | Définition |
| --- | --- |
| Ruine sur 10 ans (ou 3 ans) | Part des trajectoires où la réserve devient négative au moins une fois |
| Marge moyenne | Résultat cumulé divisé par les recettes cumulées |
| Capital requis (99 %) | Capital de départ qui évite la ruine dans 99 % des trajectoires |
| Tarif d'équilibre | Plus petit multiplicateur du tarif de départ qui garde la ruine sous 1 % ; « — » quand aucun tarif n'y parvient, parce que les usagers partent plus vite que le prix ne monte |
| Cargo an 10 | Prix médian d'un vélo-cargo après 10 ans de révisions, en €/mois |
| Occupation | Part moyenne du parc effectivement louée |

### Volumes

| Bloc | Trajectoires de 10 ans |
| --- | --- |
| 32 scénarios nommés × 20 000 trajectoires | 640 000 |
| Recherche du tarif d'équilibre (grille puis affinage, 10 000 trajectoires par point) | environ 12,8 millions |
| Analyse de sensibilité : 5 000 jeux de paramètres × 200 trajectoires | 1 000 000 |
| **Total** | **14,4 millions** |

## 2. Résultats des 32 scénarios

Sauf mention contraire, le tarif de départ est calculé avec les hypothèses de référence : chaque scénario mesure ce qui se passe quand la réalité s'en écarte. Les scénarios « tarifés à l'avance » supposent que la SCIC connaît le problème au moment de fixer le prix.

| Code | Scénario | Ruine sur 10 ans | Ruine sur 3 ans | Marge moyenne | Capital requis (99 %) | Tarif d'équilibre | Cargo an 10 (€/mois) | Occupation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S00 | Contrôle : la page telle quelle | 9,6 % | 9,1 % | 5,6 % | 81 432 € | ×1,05 | 64 | 100,0 % |
| S01 | Location, tarif de la page | 100,0 % | 100,0 % | -65,1 % | 7 288 388 € | ×1,74 | 64 | 93,7 % |
| S02 | Location, tarif recalculé (référence) | 0,0 % | 0,0 % | 5,5 % | 0 € | ×0,94 | 125 | 92,7 % |
| S03 | Référence sans révision annuelle | 65,0 % | 0,0 % | -0,6 % | 723 114 € | ×1,04 | 114 | 93,7 % |
| S04 | Casse prématurée ×2 | 0,0 % | 0,0 % | 5,4 % | 0 € | ×0,94 | 127 | 92,4 % |
| S05 | Casse prématurée ×3, coût ×2,25 | 0,6 % | 0,1 % | 4,6 % | 0 € | ×0,99 | 136 | 89,7 % |
| S06 | Main d'œuvre +40 % | 54,4 % | 24,2 % | 2,5 % | 352 916 € | ×1,14 | 154 | 81,8 % |
| S07 | Pièces ×2 | 80,8 % | 62,9 % | 1,2 % | 454 755 € | ×1,24 | 196 | 77,8 % |
| S08 | Batteries à durée courte | 12,7 % | 0,0 % | 4,1 % | 193 092 € | ×1,07 | 139 | 91,7 % |
| S09 | Coût de fabrication réaliste, découvert après tarification | 100,0 % | 82,5 % | -8,6 % | 1 875 593 € | — | 261 | 77,0 % |
| S10 | Coût de fabrication réaliste, tarifé correctement | 100,0 % | 0,0 % | -7,7 % | 1 876 476 € | — | 269 | 75,3 % |
| S11 | Rente financée à 5 % | 0,1 % | 0,0 % | 5,1 % | 0 € | ×0,96 | 131 | 91,6 % |
| S12 | Faillites de fabricants en chaîne | 0,1 % | 0,0 % | 5,0 % | 0 € | ×0,95 | 132 | 91,9 % |
| S13 | Défauts de série, faillites et vélos orphelins | 0,3 % | 0,0 % | 4,7 % | 0 € | ×0,98 | 136 | 91,3 % |
| S14 | Vol élevé, assuré | 0,0 % | 0,0 % | 5,6 % | 0 € | ×0,92 | 125 | 93,0 % |
| S15 | Vol élevé, non assuré | 0,0 % | 0,0 % | 5,2 % | 0 € | ×0,95 | 124 | 92,7 % |
| S16 | Vacance forte | 61,4 % | 1,5 % | 0,3 % | 484 337 € | — | 177 | 56,4 % |
| S17 | Fraude kilométrique massive | 1,1 % | 0,1 % | 4,5 % | 5 220 € | ×1,00 | 137 | 89,7 % |
| S18 | Usage réel +30 % de km | 0,1 % | 0,0 % | 5,3 % | 0 € | ×0,95 | 148 | 92,7 % |
| S19 | Impayés à 8 % | 3,8 % | 0,6 % | 4,2 % | 68 599 € | ×1,03 | 138 | 89,4 % |
| S20 | Inflation 5 % sans révision | 100,0 % | 0,0 % | -14,3 % | 3 131 785 € | ×1,20 | 114 | 93,7 % |
| S21 | Primes au plafond | 0,1 % | 0,0 % | 5,2 % | 0 € | ×0,96 | 129 | 91,7 % |
| S22 | Coûts de gestion fixes réalistes | 30,3 % | 8,2 % | 1,4 % | 337 616 € | ×1,20 | 141 | 76,9 % |
| S23 | Tarif unique + élasticité (spirale) | 40,9 % | 0,0 % | 0,8 % | 374 456 € | — | 155 | 65,0 % |
| S24 | Pilote 200 vélos, 2 fabricants | 0,3 % | 0,0 % | 5,4 % | 0 € | ×0,97 | 126 | 92,7 % |
| S25 | Pilote 200 vélos, 2 fabricants, faillites | 0,7 % | 0,1 % | 5,0 % | 0 € | ×0,99 | 130 | 92,2 % |
| S26 | Grande échelle : 20 000 vélos | 0,0 % | 0,0 % | 5,5 % | 0 € | ×0,93 | 125 | 92,8 % |
| S27 | Tempête modérée | 63,4 % | 19,2 % | 1,1 % | 409 439 € | ×1,20 | 168 | 69,2 % |
| S28 | Tempête sévère | 100,0 % | 100,0 % | -32,0 % | 4 122 478 € | — | 259 | 48,9 % |
| S29 | Tempête modérée, tarifée à l'avance | 3,7 % | 0,0 % | 3,0 % | 137 673 € | ×1,06 | 169 | 68,6 % |
| S30 | Coût de fabrication réaliste, usagers captifs | 0,0 % | 0,0 % | 5,8 % | 0 € | ×0,91 | 158 | 93,7 % |
| S31 | Tempête sévère, tarifée à l'avance, usagers captifs | 24,1 % | 0,0 % | 2,4 % | 359 412 € | ×1,11 | 227 | 75,3 % |

Détail des tempêtes :

- **Tempête modérée** : casse ×1,5, main d'œuvre +20 %, vol à 3 % (classique) et 6 % (cargo), 30 % de départs et 65 % de relocation, 8 % de faillite par fabricant et par an, 4 % d'impayés.
- **Tempête sévère** : casse ×2,5, main d'œuvre +40 %, pièces ×1,5, batteries ×1,6, vol à 4 % et 8 % sans assurance, 40 % de départs et 55 % de relocation, 15 % de faillite, 8 % de défauts de série, 6 % d'impayés, 25 % de fraudeurs et 4 % d'inflation.

## 3. Lecture des cas critiques

### Le contrôle valide le modèle (S00)

Avec les seuls postes de la page, le modèle retrouve les montants de la page : 1,13 M€ collectés par an et environ 19 300 € par atelier. La marge de 5,6 % est la provision de 8 % moins la casse prématurée qu'elle finance. Les 9,6 % de ruine viennent de la première année : sans capital de départ, un aléa de main d'œuvre défavorable suffit à passer sous zéro avant que la provision ne s'accumule. Un capital de départ de 81 000 €, soit 41 € par vélo, supprime ce risque.

### Le trou de la location (S01)

Appliquer le tarif de la page à un parc en location conduit à la faillite dans 100 % des trajectoires, dès la première année. Il faudrait augmenter tous les prix de 74 % pour revenir à 1 % de ruine. C'est la première correction à apporter à la page.

### Les risques que le modèle absorbe

| Famille | Scénarios | Pourquoi ça tient |
| --- | --- | --- |
| Casse et défauts | S04, S05, S13 | La casse pèse peu dans le coût total (6 à 11 € par vélo et par an) et la provision de 8 % la couvre largement |
| Faillites de fabricants | S12, S13, S25 | La rente reste due, mais les surcoûts (pièces orphelines, réformes) ne concernent qu'une partie du parc et la révision annuelle les rattrape |
| Vol | S14, S15 | Assuré, c'est un coût fixe prévisible ; non assuré, le solde de rente d'un vélo volé reste modeste parce que le coût de fabrication retenu est bas |
| Fraude, kilométrage, impayés | S17, S18, S19 | La révision annuelle corrige l'écart en un ou deux ans |
| Taille du parc | S24, S26 | Les risques qui comptent touchent tout le parc à la fois ; un petit parc n'est pas plus fragile |

La protection vient d'abord de la **révision annuelle** du tarif. Sans elle (S03), 2 % d'inflation suffisent à ruiner le fonds dans 65 % des cas en fin de période, et 5 % d'inflation (S20) le ruinent à coup sûr.

### Les risques qui font tomber le fonds

**Erreurs de coût récurrentes (S06, S07, S08, S22).** Une erreur sur un coût qui revient chaque année se rattrape trop lentement quand la hausse est plafonnée à 10 % par an. Les pièces d'usure (×2 : 81 % de ruine) et la main d'œuvre (+40 % : 54 %) sont les deux postes les plus lourds du vélo-cargo. Les coûts de structure fixes (180 000 € par an au lieu de 6 % des coûts) ruinent le fonds dans 30 % des cas.

**Vacance et spirale (S16, S23).** Quand le parc se vide, la rente et le forfait restent dus sur les vélos vacants. Augmenter le prix fait partir encore plus d'usagers : aucun tarif ne ramène la ruine sous 1 %. Sans segmentation (S23), les usagers légers paient pour les intensifs, partent, et l'occupation tombe à 65 %. Le bloc 05 de la page laissait le choix entre segmenter et assumer la solidarité ; la simulation tranche en faveur de la segmentation.

**Coût de fabrication (S09, S10, S30).** Si le vélo-cargo coûte 2 800 € à fabriquer au lieu de 1 170 €, le tarif juste monte à 148 €/mois. Découvert après coup (S09), l'écart ruine le fonds dès les trois premières années dans 82 % des cas. Connu dès le départ (S10), il ne sauve pas le fonds pour autant : au-dessus du prix de référence du marché, les usagers partent et l'occupation tombe à 75 %. Le modèle ne tient que si les usagers restent malgré le prix (S30), ce qui décrit des flottes professionnelles pour qui l'immobilisation coûte plus cher que la location.

**Tempêtes (S27 à S31).** La tempête modérée ruine le fonds dans 63 % des cas quand elle est subie, mais seulement dans 3,7 % des cas quand elle est prévue dans le tarif (S29). La tempête sévère est fatale sans usagers captifs. Même en la connaissant d'avance et avec des usagers captifs (S31), le vélo-cargo atteint 227 €/mois en dixième année et la ruine reste de 24 %.

## 4. Analyse de sensibilité globale

5 000 jeux de paramètres ont été tirés en hypercube latin, une méthode qui couvre chaque plage régulièrement, dans les plages plausibles ci-dessous. Chaque jeu a été simulé sur 200 trajectoires avec le tarif de référence et la révision annuelle. Le classement mesure la corrélation de rang (Spearman) entre chaque paramètre et la marge du fonds.

| Rang | Paramètre | Plage explorée | Corrélation avec la marge | Ruine, quintile bas | Ruine, quintile haut |
| --- | --- | --- | --- | --- | --- |
| 1 | Coût de fabrication du vélo-cargo | 1 000 à 3 000 € | -0,52 | 72 % | 99 % |
| 2 | Consommation de pièces d'usure | ×0,5 à ×1,7 | -0,36 | 72 % | 98 % |
| 3 | Heures de main d'œuvre par 1 000 km | ×0,75 à ×1,35 | -0,33 | 74 % | 97 % |
| 4 | Taux de relocation des vélos vacants | 55 à 95 % | +0,30 | 94 % | 84 % |
| 5 | Inflation | 0 à 4 % | +0,28 | 88 % | 90 % |
| 6 | Départs de locataires par an | 10 à 35 % | -0,22 | 84 % | 92 % |
| 7 | Coûts de structure fixes | 0 à 150 000 € | -0,21 | 81 % | 93 % |
| 8 | Taux horaire moyen | 40 à 58 € | -0,20 | 80 % | 94 % |
| 9 | Kilométrage | ×0,7 à ×1,3 | +0,17 | 93 % | 84 % |
| 10 | Impayés | 0 à 6 % | -0,16 | 84 % | 91 % |
| 11 | Vieillissement (heures par année d'âge) | 0 à 8 % | -0,13 | 83 % | 92 % |
| 12 | Taux de financement de la rente | 0 à 6 % | -0,12 | 85 % | 90 % |
| 13 | Durée de vie des batteries | ×0,5 à ×1,7 | -0,09 | 86 % | 92 % |
| 14 | Part de fraudeurs | 0 à 30 % | -0,09 | 85 % | 92 % |
| 15 | Coût de fabrication du vélo classique | 380 à 650 € | -0,09 | 86 % | 91 % |
| 16 | Réforme des vélos orphelins | 0 à 15 % par an | -0,07 | 88 % | 89 % |
| 17 | Score moyen (primes) | 60 à 95 | -0,06 | 86 % | 90 % |
| 18 | Faillite annuelle par fabricant | 0 à 12 % | -0,05 | 86 % | 90 % |
| 19 | Casse prématurée | ×0,5 à ×3 | -0,04 | 86 % | 90 % |
| 20 | Vol des vélos-cargos | 2 à 7 % | +0,03 | 89 % | 88 % |
| 21 | Vol des vélos classiques | 1 à 4 % | -0,01 | 88 % | 89 % |
| 22 | Défauts de série | 0 à 8 % | -0,01 | 87 % | 89 % |

Sur l'ensemble de cet espace, la probabilité de ruine moyenne est de **88 %** : seuls 6,5 % des jeux de paramètres restent sous 5 % de ruine, et la marge médiane est de -17 %. Ce chiffre ne dit pas que le modèle est condamné. Il dit que les hypothèses de la page sont du côté optimiste des plages plausibles, surtout pour le coût de fabrication, et qu'aucun tarif ne doit être fixé avant d'avoir mesuré les cinq premiers paramètres du classement.

Probabilité de ruine selon les deux paramètres les plus influents :

| Coût du cargo ↓ / Pièces → | ×0,5 à ×0,8 | ×0,8 à ×1,1 | ×1,1 à ×1,4 | ×1,4 à ×1,7 |
| --- | --- | --- | --- | --- |
| 1 000 à 1 500 € | 47 % | 73 % | 83 % | 94 % |
| 1 500 à 2 000 € | 68 % | 83 % | 93 % | 98 % |
| 2 000 à 2 500 € | 87 % | 96 % | 98 % | 100 % |
| 2 500 à 3 000 € | 94 % | 99 % | 100 % | 100 % |

Les risques de sinistre (vol, casse, défauts de série, faillites) sont en bas du classement. C'est cohérent avec les scénarios nommés : le modèle est bien protégé contre les accidents et mal protégé contre les erreurs de prix de revient.

## 5. Compétitivité du prix

Le prix de référence du marché conditionne la survie du fonds. Pour le situer, voici des ordres de grandeur illustratifs du coût de possession, à vérifier avec les usagers (voir le [registre des acteurs](acteurs.md)) :

| Usage | Tarif de référence | Véligo Location (subventionné) | Coût de possession estimé |
| --- | --- | --- | --- |
| Léger, vélo classique | 52 €/mois | 10 €/mois (mécanique) | Environ 20 à 25 €/mois : vélo à 800 € sur 10 ans, entretien, antivol |
| Intensif, vélo-cargo électrique | 114 €/mois | Jusqu'à 88 €/mois | Environ 100 à 120 €/mois : vélo à 3 500 à 7 000 €, batterie de 500 à 1 000 € tous les 4 à 5 ans, entretien professionnel, assurance |

Pour le vélo-cargo intensif, le tarif de référence est au niveau du coût de possession et apporte un service en plus : suivi, garantie, pas d'immobilisation ni d'avance d'argent. Pour l'usage léger, il coûte environ deux fois plus cher que posséder son vélo. C'est là que le risque de départs est le plus fort.

## 6. Ce que la simulation recommande

1. **Corriger la page** : le tarif de location est d'environ 52 €/mois pour un usage léger et 114 €/mois pour un vélo-cargo, pas 36 et 64 €/mois. *Fait le 2026-09-22 : la page affiche désormais ces tarifs et le fonds de 1,68 M€ par an.*
2. **Commencer par les flottes professionnelles de vélos-cargos.** Ce sont les usagers pour qui le service vaut le plus et qui partent le moins quand le prix monte (S30). L'usage léger viendra ensuite, si le pilote montre que le service justifie l'écart avec la possession.
3. **Ne fixer aucun tarif avant d'avoir mesuré** le coût de fabrication réel du vélo-cargo, la consommation de pièces, les heures d'atelier par 1 000 km et les taux de départ et de relocation.
4. **Inscrire la révision annuelle dans les statuts**, avec une clause de révision exceptionnelle au-delà de 10 % quand un coût dérive durablement (S06, S07).
5. **Segmenter le tarif** par catégorie de vélo et d'usage dès le départ (S23).
6. **Prévoir une réserve de démarrage d'environ 205 € par vélo**, soit 410 000 € pour 2 000 vélos. Elle couvre la tempête modérée à 99 % (S27) et le démarrage sans provision accumulée (S00). C'est ce montant qu'il faut demander aux collectivités et à l'ADEME en préfinancement.
7. **Assurer le parc contre le vol** : l'assurance ne change presque rien à l'équilibre, mais elle transforme un risque en coût fixe prévisible.
8. **Obtenir des fabricants une garantie de disponibilité des pièces**, par exemple un dépôt de plans et d'outillage auprès de la SCIC, pour limiter le coût d'une faillite.

## 7. Données à collecter pendant le pilote

| Donnée | Paramètre | Source probable |
| --- | --- | --- |
| Coût de fabrication d'un vélo-cargo labellisé | `cout_intensif` | Douze Cycles, Manufacture Française du Cycle, Arcade Cycles |
| Consommation de pièces par 1 000 km | `pieces_km_*` | Atelier pilote, Cyclonova (Véligo) |
| Heures d'atelier par 1 000 km et selon l'âge | `h_1000km_*`, `vieillissement` | La Fabrique des Cyclistes, Cyclonova |
| Départs et relocation | `churn`, `remplissage` | Véligo, Swapfiets, Les Boîtes à Vélo |
| Durée de vie des batteries | `batterie_facteur` | Fabricants, Cyclonova |
| Prime d'assurance vol d'un parc | `assurance_taux` | Mutuelle d'assurance |
| Coûts de structure de la SCIC | `gestion_fixe` | CG Scop, SCIC existantes |
| Disposition à payer | Prix de référence du marché | Les Boîtes à Vélo, FUB |

## 8. Limites du modèle

- **Pas annuel** : la trésorerie infra-annuelle (décalage entre cotisations mensuelles et factures d'atelier) n'est pas simulée.
- **Hypothèses illustratives** : seuls les kilométrages, les prix Véligo, les prix publics des vélos-cargos et les ordres de grandeur du vol et des batteries viennent de sources ; le reste est à caler en pilote.
- **Élasticité simplifiée** : les départs augmentent en proportion de l'écart au prix de référence, sans distinguer les profils d'usagers ni la concurrence locale.
- **Corrélations** : les risques sont indépendants, sauf dans les tempêtes où ils sont combinés à la main.
- **Côté fabricant non modélisé** : la simulation ne mesure pas le risque que prend un fabricant en acceptant une rente sur 8 à 10 ans d'une SCIC qui peut elle-même faire faillite.
- **Pas de subventions** : Bonus Répar Cycle, aides de l'ADEME et des collectivités ne sont pas comptés. Ils amélioreraient l'équilibre, mais le modèle doit tenir sans eux.

## Reproduire la simulation

```sh
uv run simulation/simulation.py            # campagne complète, de quelques minutes à 45 minutes selon la machine
uv run simulation/simulation.py --rapide   # contrôle en quelques secondes, volumes réduits
```

Les hypothèses de référence sont regroupées dans le dictionnaire `BASE`, les scénarios dans `SCENARIOS` et les plages de sensibilité dans `PLAGES`. La graine aléatoire (2026 par défaut) rend les résultats reproductibles.
