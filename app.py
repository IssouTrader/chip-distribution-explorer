"""
Prototype de site web -- Chip Distribution Explorer

Lancement local :
    pip install streamlit yfinance requests pandas matplotlib deep-translator
    streamlit run app.py

Pour que le thème visuel (fond marine, accent doré) s'applique, le
dossier ".streamlit" (contenant config.toml) doit être dans le même
dossier que ce fichier app.py.
"""

import bisect
import os
import json
from datetime import date as ddate
from urllib.parse import urlparse

import requests
import yfinance as yf
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HEADERS = {"User-Agent": "ChipDistributionExplorer/1.0 (contact: issoutrader.app@gmail.com)"}

# ---------------------------------------------------------------------
# Textes de l'interface, en français et en anglais
# ---------------------------------------------------------------------
STRINGS = {
    "fr": {
        "app_title": "Chip Distribution Explorer",
        "app_caption": "Tape un ticker ou le nom de l'entreprise pour voir la répartition estimée du coût moyen de ses actionnaires actuels.",
        "ticker_label": "Ticker ou nom de l'entreprise",
        "ticker_placeholder": "ex: SIDU, Tesla, ID Logistics...",
        "multiple_matches": "Plusieurs entreprises correspondent à \"{query}\" -- sélectionne la bonne :",
        "select_placeholder": "Choisis une entreprise...",
        "confirm_button": "Confirmer",
        "generate_button": "Générer le rapport",
        "spinner": "Analyse de {ticker} en cours...",
        "error_not_found": "Ticker '{ticker}' introuvable dans la base SEC. Vérifie l'orthographe.",
        "error_sec_unreachable": "Impossible de joindre les serveurs de la SEC pour le moment. Réessaie dans quelques instants.",
        "error_no_sec_data": "Pas de données SEC exploitables pour '{ticker}'.",
        "international_note": "⚠️ Ce ticker n'est pas enregistré auprès de la SEC (marché non-US, ex: XETRA, Euronext). Le nombre d'actions en circulation est traité comme constant, sans historique de dilution -- résultat moins précis que les 14 tickers de référence.",
        "error_compute": "Erreur lors du calcul : {err}",
        "about_company": "À propos",
        "analysis_title": "Analyse",
        "analysis_text": "À la date du {date}, le prix de clôture est de **{price:.2f}**. Le modèle estime que **{gain:.1f}%** du flottant est en gain latent, et **{loss:.1f}%** en perte latente. La zone de coût moyen la plus dense se situe autour de **{top_price:.2f}** ({top_pct:.1f}% du flottant). {position} {gain_perte_txt}",
        "distribution_title": "Distribution estimée actuelle",
        "chart_xlabel": "% des actions estimées à ce prix",
        "chart_title": "{n} séances analysées",
        "chart_trimmed_note": "(zone recadrée sur les {pct:.1f}% de flottant les plus représentés)",
        "current_price_label": "Prix actuel : {price:.2f}",
        "price_box_label": "PRIX ACTUEL",
        "position_center": "Le prix actuel se situe au cœur de la zone la plus dense.",
        "position_above": "La zone la plus dense est au-dessus du prix actuel (à {pct:.0f}% plus haut).",
        "position_below": "La zone la plus dense est en dessous du prix actuel (à {pct:.0f}% plus bas).",
        "majority_loss": "Une majorité d'actionnaires est en perte latente.",
        "majority_gain": "Une majorité d'actionnaires est en gain latent.",
        "balanced": "La répartition gain/perte est proche de l'équilibre.",
        "disclaimer": "⚠️ Ceci est une estimation statistique, pas une mesure réelle des positions, et ne constitue pas un conseil en investissement.",
        "lang_selector": "Langue / Language",
        "gain_badge": "{v:.0f}% DES ACTIONNAIRES EN GAIN",
        "loss_badge": "{v:.0f}% DES ACTIONNAIRES EN PERTE",
        "stat_52w_high": "PLUS HAUT 52 SEM.",
        "stat_52w_low": "PLUS BAS 52 SEM.",
        "stat_range_pos": "POSITION DANS LE RANGE",
        "stat_30d": "VARIATION 30 SÉANCES",
        "analysis_extended": "Sur les 52 dernières semaines, le titre a évolué entre **{low:.2f}** et **{high:.2f}**, et le prix actuel se situe à **{range_pos:.0f}%** de cette fourchette (0% = plus bas, 100% = plus haut). {trend_txt} **{concentration:.0f}%** du flottant est concentré à moins de 10% du prix actuel, ce qui {concentration_txt}. {secondary_txt}",
        "trend_up": "Sur les 30 dernières séances, le titre a progressé de **{v:.1f}%**.",
        "trend_down": "Sur les 30 dernières séances, le titre a reculé de **{v:.1f}%**.",
        "trend_flat": "Le titre est resté globalement stable sur les 30 dernières séances ({v:+.1f}%).",
        "concentration_high": "traduit une base actionnariale resserrée autour du niveau actuel (davantage de sensibilité aux mouvements de prix courts)",
        "concentration_low": "traduit une base actionnariale plus dispersée sur différents niveaux de prix historiques",
        "secondary_zone": "Une deuxième zone notable se situe autour de **{price:.2f}** ({pct:.1f}% du flottant).",
        "founded_label": "FONDÉE EN",
        "listed_label": "COTÉE DEPUIS",
        "sector_label": "SECTEUR",
        "employees_label": "EMPLOYÉS",
        "market_cap_label": "CAPITALISATION",
        "revenue_label": "CHIFFRE D'AFFAIRES",
        "net_income_label": "RÉSULTAT NET",
        "fundamentals_title": "Fondamentaux",
    },
    "en": {
        "app_title": "Chip Distribution Explorer",
        "app_caption": "Type a ticker or company name to see the estimated cost-basis distribution of its current shareholders.",
        "ticker_label": "Ticker or company name",
        "ticker_placeholder": "e.g. SIDU, Tesla, ID Logistics...",
        "multiple_matches": "Several companies match \"{query}\" -- pick the right one:",
        "select_placeholder": "Choose a company...",
        "confirm_button": "Confirm",
        "generate_button": "Generate report",
        "spinner": "Analyzing {ticker}...",
        "error_not_found": "Ticker '{ticker}' not found in the SEC database. Check the spelling.",
        "error_sec_unreachable": "Could not reach SEC servers right now. Please try again shortly.",
        "error_no_sec_data": "No usable SEC data for '{ticker}'.",
        "international_note": "⚠️ This ticker is not SEC-registered (non-US market, e.g. XETRA, Euronext). Shares outstanding are treated as constant, with no dilution history -- less precise than the 14 reference tickers.",
        "error_compute": "Error during computation: {err}",
        "about_company": "About",
        "analysis_title": "Analysis",
        "analysis_text": "As of {date}, the closing price is **{price:.2f}**. The model estimates that **{gain:.1f}%** of the float is at an unrealized gain, and **{loss:.1f}%** at an unrealized loss. The densest cost-basis zone is around **{top_price:.2f}** ({top_pct:.1f}% of the float). {position} {gain_perte_txt}",
        "distribution_title": "Current estimated distribution",
        "chart_xlabel": "% of shares estimated at this price",
        "chart_title": "{n} trading days analyzed",
        "chart_trimmed_note": "(zoomed to the {pct:.1f}% of float that is most represented)",
        "current_price_label": "Current price: {price:.2f}",
        "price_box_label": "CURRENT PRICE",
        "position_center": "The current price sits right in the middle of the densest zone.",
        "position_above": "The densest zone is above the current price (about {pct:.0f}% higher).",
        "position_below": "The densest zone is below the current price (about {pct:.0f}% lower).",
        "majority_loss": "A majority of shareholders are at an unrealized loss.",
        "majority_gain": "A majority of shareholders are at an unrealized gain.",
        "balanced": "The gain/loss split is close to balanced.",
        "disclaimer": "⚠️ This is a statistical estimate, not a real measurement of positions, and does not constitute investment advice.",
        "lang_selector": "Langue / Language",
        "gain_badge": "{v:.0f}% OF SHAREHOLDERS IN GAIN",
        "loss_badge": "{v:.0f}% OF SHAREHOLDERS IN LOSS",
        "stat_52w_high": "52W HIGH",
        "stat_52w_low": "52W LOW",
        "stat_range_pos": "POSITION IN RANGE",
        "stat_30d": "30-DAY CHANGE",
        "analysis_extended": "Over the past 52 weeks, the stock has traded between **{low:.2f}** and **{high:.2f}**, and the current price sits at **{range_pos:.0f}%** of that range (0% = low, 100% = high). {trend_txt} **{concentration:.0f}%** of the float is concentrated within 10% of the current price, which {concentration_txt}. {secondary_txt}",
        "trend_up": "Over the last 30 trading days, the stock has gained **{v:.1f}%**.",
        "trend_down": "Over the last 30 trading days, the stock has lost **{v:.1f}%**.",
        "trend_flat": "The stock has been broadly stable over the last 30 trading days ({v:+.1f}%).",
        "concentration_high": "suggests a tightly clustered shareholder base around the current level (more sensitivity to short-term price moves)",
        "concentration_low": "suggests a more dispersed shareholder base across different historical price levels",
        "secondary_zone": "A second notable zone sits around **{price:.2f}** ({pct:.1f}% of the float).",
        "founded_label": "FOUNDED",
        "listed_label": "LISTED SINCE",
        "sector_label": "SECTOR",
        "employees_label": "EMPLOYEES",
        "market_cap_label": "MARKET CAP",
        "revenue_label": "REVENUE",
        "net_income_label": "NET INCOME",
        "fundamentals_title": "Fundamentals",
    },
}

# ---------------------------------------------------------------------
# Base de connaissance : les 14 tickers déjà analysés en profondeur
# ---------------------------------------------------------------------
CURATED = {
    "SIDU": {"start": "2023-12-20", "bucket": 0.10, "domain": "sidusspace.com", "currency": "USD", "full_name": "Sidus Space", "founded": None, "listed": "2021-12-14",
        "checkpoints": [("2023-12-20",778679),("2026-02-20",66419852),("2026-06-12",80860000),("2026-07-10",97350000),("2026-07-20",100450000)],
        "events": {"2024-02-01":(1251700,4.50),"2024-11-14":(5600000,1.25),"2025-07-29":(7143000,1.05),
                   "2025-12-24":(19230800,1.30),"2025-12-29":(10800000,1.50),"2026-04-21":(13453700,4.35),"2026-05-29":(19685039,5.08)},
        "description": {
            "fr": "Sidus Space conçoit et fabrique des composants et structures pour satellites, et fournit des services liés au spatial et à la défense, avec des clients incluant des agences gouvernementales et des acteurs du « New Space ». Depuis son regroupement d'actions de décembre 2023, la société a financé sa croissance par une succession de levées de fonds, ce qui a fortement dilué ses actionnaires historiques mais lui a permis de multiplier ses capacités de production.",
            "en": "Sidus Space designs and manufactures satellite components and structures, and provides space- and defense-related services, with clients including government agencies and “New Space” players. Since its December 2023 reverse stock split, the company has financed its growth through a series of capital raises, heavily diluting long-standing shareholders while expanding its production capacity.",
        }},
    "ELDN": {"start": "2021-12-01", "bucket": 0.10, "domain": "eledon.com", "currency": "USD", "full_name": "Eledon Pharmaceuticals", "founded": 2014, "listed": "2021-01-01",
        "checkpoints": [("2021-03-23",13716406),("2026-05-07",77187823)],
        "events": {"2025-11-13": (15152485, 1.65)},
        "description": {
            "fr": "Eledon Pharmaceuticals est une biotech clinique qui développe tegoprubart, un anticorps destiné à prévenir le rejet dans la transplantation d'organes, avec un programme additionnel dans la sclérose latérale amyotrophique (SLA). Le titre a subi un choc majeur le 7 novembre 2025 lorsque l'essai clinique de phase 2 BESTOW n'a pas atteint son critère principal, entraînant une chute de près de 50% suivie d'une levée de fonds d'urgence pour poursuivre le développement du programme SLA.",
            "en": "Eledon Pharmaceuticals is a clinical-stage biotech developing tegoprubart, an antibody aimed at preventing organ transplant rejection, with an additional program in ALS (amyotrophic lateral sclerosis). The stock suffered a major shock on November 7, 2025 when the Phase 2 BESTOW trial missed its primary endpoint, triggering a near-50% drop followed by an emergency capital raise to continue funding the ALS program.",
        }},
    "DFDV": {"start": "2025-05-20", "bucket": 0.20, "domain": "defidevcorp.com", "currency": "USD", "full_name": "DeFi Development Corp", "founded": 2018, "listed": "2023-07-27",
        "checkpoints": [("2025-05-20",14083209),("2025-08-14",21045049),("2025-11-19",31401212),("2026-03-30",29497394),("2026-05-19",30118205)],
        "events": {},
        "description": {
            "fr": "DeFi Development Corp est une société de trésorerie cotée dont la stratégie consiste à accumuler et détenir du Solana (SOL), sur le modèle popularisé par MicroStrategy pour le Bitcoin. Anciennement Janover Inc., une plateforme fintech immobilière, la société a opéré un pivot stratégique complet le 7 avril 2025 (le titre avait alors bondi de +842% en une seule séance), et finance depuis ses achats de SOL par des émissions d'actions répétées.",
            "en": "DeFi Development Corp is a publicly listed treasury company whose strategy is to accumulate and hold Solana (SOL), following the model popularized by MicroStrategy for Bitcoin. Formerly Janover Inc., a real-estate fintech platform, the company underwent a full strategic pivot on April 7, 2025 (the stock jumped +842% that single session), and has since funded its SOL purchases through repeated share issuances.",
        }},
    "RCAT": {"start": "2021-04-30", "bucket": 0.20, "domain": "redcatholdings.com", "currency": "USD", "full_name": "Red Cat Holdings", "founded": 1984, "listed": "2021-04-30",
        "checkpoints": [("2021-03-22",27460000),("2026-05-01",122742361)],
        "events": {},
        "description": {
            "fr": "Red Cat Holdings fabrique des drones et systèmes robotiques pour la défense, la sécurité nationale et des applications commerciales (gammes Black Widow, Teal 2, Edge 130 Blue). L'entité existe légalement depuis 1984 mais n'a rejoint le Nasdaq qu'en avril 2021 ; avant cette date, elle n'était qu'une coquille quasi inactive sur les marchés de gré à gré (OTC).",
            "en": "Red Cat Holdings manufactures drones and robotic systems for defense, national security, and commercial applications (Black Widow, Teal 2, Edge 130 Blue product lines). The legal entity has existed since 1984 but only joined the Nasdaq in April 2021; before that, it was a largely inactive shell trading over-the-counter (OTC).",
        }},
    "AIRJ": {"start": "2024-03-14", "bucket": 0.20, "domain": "airjoule.com", "currency": "USD", "full_name": "AirJoule Technologies", "founded": None, "listed": "2024-03-14",
        "checkpoints": [("2024-03-14",55843165),("2026-05-01",68472740)],
        "events": {},
        "description": {
            "fr": "AirJoule Technologies développe une technologie de captation d'eau atmosphérique par sorption, utilisée notamment pour le refroidissement des data centers IA, avec des partenariats industriels auprès de GE Vernova et Carrier. La société est issue d'une fusion SPAC clôturée le 14 mars 2024, initialement sous le nom « Montana Technologies » avant d'être renommée AirJoule Technologies en novembre 2024.",
            "en": "AirJoule Technologies develops sorption-based atmospheric water harvesting technology, used notably for cooling AI data centers, with industrial partnerships including GE Vernova and Carrier. The company emerged from a SPAC merger that closed on March 14, 2024, initially under the name “Montana Technologies” before being renamed AirJoule Technologies in November 2024.",
        }},
    "CIFR": {"start": "2021-08-10", "bucket": 0.60, "domain": "cipher.digital", "currency": "USD", "full_name": "Cipher Digital", "founded": 2021, "listed": "2021-08-10",
        "checkpoints": [("2021-08-10",246381119),("2026-05-04",409049197)],
        "events": {},
        "description": {
            "fr": "Cipher Digital (renommée depuis Cipher Mining en février 2026) a opéré l'un des pivots les plus marquants du secteur minier Bitcoin coté, passant de revenus volatils liés au minage vers l'hébergement d'infrastructure IA/HPC sous contrats long terme avec des clients comme AWS, Google et Fluidstack. La société est issue d'une fusion SPAC clôturée à l'été 2021.",
            "en": "Cipher Digital (renamed from Cipher Mining in February 2026) has undertaken one of the most notable pivots in the publicly listed Bitcoin mining sector, moving from volatile mining revenue toward hosting AI/HPC infrastructure under long-term contracts with clients including AWS, Google, and Fluidstack. The company emerged from a SPAC merger that closed in the summer of 2021.",
        }},
    "TSLA": {"start": "2022-08-25", "bucket": 2.0, "domain": "tesla.com", "currency": "USD", "full_name": "Tesla", "founded": 2003, "listed": "2010-06-29",
        "checkpoints": [("2022-08-25",3164000000),("2026-07-16",3949547394)],
        "events": {},
        "description": {
            "fr": "Tesla conçoit, fabrique et vend des véhicules électriques, des systèmes de stockage d'énergie et des panneaux solaires, tout en exploitant le plus grand réseau mondial de bornes de recharge rapide (Superchargers). Dirigée par Elon Musk, l'entreprise a réalisé deux divisions d'actions (5-pour-1 en 2020, 3-pour-1 en 2022) reflétant sa forte croissance boursière depuis son introduction en bourse en 2010.",
            "en": "Tesla designs, manufactures and sells electric vehicles, energy storage systems, and solar panels, while operating the world's largest fast-charging network (Superchargers). Led by Elon Musk, the company has carried out two stock splits (5-for-1 in 2020, 3-for-1 in 2022), reflecting its strong share-price growth since its 2010 IPO.",
        }},
    "UBER": {"start": "2019-05-10", "bucket": 0.50, "domain": "uber.com", "currency": "USD", "full_name": "Uber Technologies", "founded": 2009, "listed": "2019-05-10",
        "checkpoints": [("2019-05-22",1695552739),("2026-05-01",2035599013)],
        "events": {},
        "description": {
            "fr": "Uber Technologies exploite des plateformes de mobilité (VTC), de livraison de repas (Uber Eats) et de fret, présentes dans plus de 70 pays. Après des années centrées sur la croissance des parts de marché au détriment de la rentabilité, le groupe a atteint une profitabilité durable au cours des dernières années.",
            "en": "Uber Technologies operates ride-hailing, food delivery (Uber Eats), and freight platforms across more than 70 countries. After years prioritizing market-share growth over profitability, the company has achieved sustained profitability in recent years.",
        }},
    "NVAX": {"start": "2019-08-01", "bucket": 0.10, "domain": "novavax.com", "currency": "USD", "full_name": "Novavax", "founded": 1987, "listed": "1995-01-01",
        "checkpoints": [("2019-07-31",23922326),("2026-04-30",164438119)],
        "events": {},
        "description": {
            "fr": "Novavax est une biotech spécialisée dans le développement de vaccins, portée sur le devant de la scène par son vaccin protéique contre la COVID-19 (Nuvaxovid). La société a une longue histoire, marquée par des difficultés répétées d'essais cliniques et de commercialisation bien antérieures à la pandémie.",
            "en": "Novavax is a biotech specialized in vaccine development, propelled into the spotlight by its protein-based COVID-19 vaccine (Nuvaxovid). The company has a long history marked by repeated clinical-trial and commercialization setbacks that predate the pandemic.",
        }},
    "IONQ": {"start": "2021-01-04", "bucket": 0.50, "domain": "ionq.com", "currency": "USD", "full_name": "IonQ", "founded": 2015, "listed": "2021-01-04",
        "checkpoints": [("2021-11-08",192487104),("2026-04-29",373269948)],
        "events": {},
        "description": {
            "fr": "IonQ développe des ordinateurs quantiques à base d'ions piégés, et commercialise l'accès à ses machines via le cloud, notamment via des partenariats avec les grands fournisseurs cloud (AWS, Azure, Google Cloud). C'est l'une des rares entreprises pure-play de l'informatique quantique cotées en bourse.",
            "en": "IonQ develops trapped-ion quantum computers and sells access to its machines via the cloud, including through partnerships with major cloud providers (AWS, Azure, Google Cloud). It is one of the few publicly traded pure-play quantum computing companies.",
        }},
    "HAFN": {"start": "2024-04-10", "bucket": 0.30, "domain": "hafniabw.com", "currency": "USD", "full_name": "Hafnia Limited", "founded": 2019, "listed": "2024-04-10",
        "checkpoints": [("2024-12-31",502924476),("2025-12-31",497989642)],
        "events": {},
        "description": {
            "fr": "Hafnia Limited est un armateur spécialisé dans le transport maritime de produits pétroliers raffinés, l'un des plus grands au monde dans ce segment. Née en 2019 de la fusion de Hafnia Tankers et BW Tankers, son chiffre d'affaires est étroitement lié aux cycles des taux de fret maritime.",
            "en": "Hafnia Limited is a shipowner specialized in the seaborne transport of refined petroleum products, one of the largest in the world in this segment. Formed in 2019 through the merger of Hafnia Tankers and BW Tankers, its revenue is closely tied to shipping freight-rate cycles.",
        }},
    "GPRO": {"start": "2014-06-26", "bucket": 0.10, "domain": "gopro.com", "currency": "USD", "full_name": "GoPro", "founded": 2002, "listed": "2014-06-26",
        "checkpoints": [("2014-06-30",83000000),("2026-04-30",144720000)],
        "events": {},
        "description": {
            "fr": "GoPro conçoit et commercialise des caméras d'action et accessoires grand public, avec un service d'abonnement complémentaire. Le titre a connu un déclin structurel de longue durée depuis son introduction en bourse en 2014, à mesure que les smartphones ont érodé une partie de son marché historique.",
            "en": "GoPro designs and sells consumer action cameras and accessories, with a complementary subscription service. The stock has experienced a long structural decline since its 2014 IPO, as smartphones eroded part of its historical market.",
        }},
    "PLTR": {"start": "2021-02-19", "bucket": 3.0, "domain": "palantir.com", "currency": "USD", "full_name": "Palantir Technologies", "founded": 2003, "listed": "2020-09-30",
        "checkpoints": [("2021-02-19",1750000000),("2026-02-10",2290000000)],
        "events": {},
        "description": {
            "fr": "Palantir Technologies développe des plateformes logicielles d'analyse de données et d'intelligence artificielle (Foundry, Gotham), pour des clients gouvernementaux — notamment dans la défense — et des entreprises. La société est entrée en bourse via une introduction directe en septembre 2020, sans passer par une souscription bancaire traditionnelle.",
            "en": "Palantir Technologies develops data analytics and AI software platforms (Foundry, Gotham) for government clients — notably in defense — and enterprises. The company went public via a direct listing in September 2020, bypassing a traditional underwritten IPO.",
        }},
    "IDL.PA": {"start": "2012-04-18", "bucket": 5.0, "domain": "id-logistics.com", "currency": "EUR", "full_name": "ID Logistics Group", "founded": 2001, "listed": "2012-04-18",
        "checkpoints": [("2019-12-31",5645301),("2023-05-31",6173328),("2024-06-30",6173328),("2025-09-30",6548328),("2025-12-31",6548328),("2026-06-30",6550826)],
        "events": {"2024-09-09": (375000, 360.0)},
        "description": {
            "fr": "ID Logistics Group est un prestataire de logistique contractuelle (préparation de commandes, entreposage, transport) présent dans plus de 450 sites à travers le monde. Cotée depuis avril 2012, la société a connu une croissance boursière longue et régulière avec une dilution des actionnaires restée minime comparée aux standards du secteur.",
            "en": "ID Logistics Group is a contract logistics provider (order fulfillment, warehousing, transport) present across more than 450 sites worldwide. Listed since April 2012, the company has delivered long, steady share-price growth with shareholder dilution that has remained minimal compared to sector norms.",
        }},
}

# ---------------------------------------------------------------------
# Repli générique : SEC seule, pour un ticker non couvert
# ---------------------------------------------------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def get_all_sec_tickers():
    # 1) Fichier local embarqué dans le dépôt -- instantané, aucune dépendance
    #    réseau. C'est la source principale une fois que ce fichier est présent.
    local_path = os.path.join(os.path.dirname(__file__), "company_tickers.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, encoding="utf-8") as f:
                return list(json.load(f).values())
        except Exception:
            pass  # fichier local corrompu -- on retombe sur la SEC en direct

    # 2) Repli : appel direct à la SEC (utilisé si le fichier local n'est pas
    #    encore ajouté au dépôt, ou pour couvrir les tickers très récents)
    url = "https://www.sec.gov/files/company_tickers.json"
    last_error = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            return list(r.json().values())
        except Exception as e:
            last_error = e
    raise last_error

def get_cik(ticker):
    entries = get_all_sec_tickers()  # laisse l'exception remonter si la SEC est injoignable
    for entry in entries:
        if entry["ticker"].upper() == ticker.upper():
            return str(entry["cik_str"]).zfill(10)

    # Pas trouvé dans le fichier local -- peut simplement être une entreprise
    # trop récente pour figurer dans la photo figée. Un seul appel ciblé en
    # direct à la SEC, spécifique à ce ticker, pour couvrir ce cas sans
    # dépendre du fichier complet.
    try:
        url2 = "https://www.sec.gov/files/company_tickers.json"
        r = requests.get(url2, headers=HEADERS, timeout=20)
        r.raise_for_status()
        for entry in r.json().values():
            if entry["ticker"].upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        pass
    return None

@st.cache_data(ttl=86400, show_spinner=False)
def get_international_companies():
    local_path = os.path.join(os.path.dirname(__file__), "international_companies.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def search_by_name(query, limit=8):
    """Cherche une entreprise par son nom (pas son ticker) -- d'abord parmi
    les 14 tickers déjà couverts en détail, puis les grandes capitalisations
    CAC 40/DAX 40/Nikkei 225, puis dans la base SEC complète (Nasdaq/NYSE),
    en repli."""
    query_lower = query.strip().lower()
    if len(query_lower) < 2:
        return []
    results = []
    seen_tickers = set()
    for ticker, cfg in CURATED.items():
        name = cfg.get("full_name", ticker)
        if query_lower in name.lower() and ticker not in seen_tickers:
            results.append((ticker, name))
            seen_tickers.add(ticker)
    for ticker, name in get_international_companies().items():
        if len(results) >= limit:
            break
        if query_lower in name.lower() and ticker not in seen_tickers:
            results.append((ticker, name))
            seen_tickers.add(ticker)
    try:
        for entry in get_all_sec_tickers():
            if len(results) >= limit:
                break
            if query_lower in entry["title"].lower() and entry["ticker"].upper() not in seen_tickers:
                results.append((entry["ticker"].upper(), entry["title"]))
                seen_tickers.add(entry["ticker"].upper())
    except Exception:
        pass
    return results[:limit]

def get_sec_checkpoints(cik):
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/EntityCommonStockSharesOutstanding.json"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json()
    rows = sorted({(e["end"], e["val"]) for e in data["units"]["shares"]})
    return [(d, v) for d, v in rows]

def get_international_shares(ticker):
    """Repli pour les tickers non enregistrés à la SEC (XETRA, Euronext hors
    IDL.PA, Tokyo, LSE, etc.) -- un seul chiffre actuel, sans historique de
    dilution, faute d'équivalent gratuit de l'API SEC pour ces marchés."""
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info
            shares = info.get("sharesOutstanding")
            if shares:
                today = ddate.today().strftime("%Y-%m-%d")
                return [(today, int(shares))]
            return None  # ticker valide mais pas de donnée -- inutile de réessayer
        except Exception:
            continue
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_yf_info(ticker):
    """Un seul point d'accès à yf.Ticker(...).info, avec tentatives
    automatiques et mise en cache -- évite de dupliquer cet appel (utilisé
    à la fois pour la description, le logo et les fondamentaux) et réduit
    le risque d'échec réseau sur l'hébergement partagé."""
    last_error = None
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info
            if info and len(info) > 3:  # une réponse vide/quasi-vide n'est pas exploitable
                return info
        except Exception as e:
            last_error = e
    return {}

def get_company_description(ticker, target_lang):
    info = get_yf_info(ticker)
    text = info.get("longBusinessSummary", None)
    if not text:
        return None, info.get("website")
    if target_lang == "en":
        return text, info.get("website")
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="fr").translate(text), info.get("website")
    except Exception:
        return text, info.get("website")

def fetch_logo_bytes(domain):
    if not domain:
        return None
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    # Clearbit (logo.clearbit.com) a fermé définitivement le 1er décembre 2025 -- on
    # utilise deux services gratuits toujours actifs, sans clé API, avec repli automatique.
    candidates = [
        f"https://icons.duckduckgo.com/ip3/{domain}.ico",
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
    ]
    for url in candidates:
        try:
            r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 200:  # évite les icônes "vides" par défaut
                return r.content
        except Exception:
            continue
    return None

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF", "CAD": "C$"}
def fmt_currency(value, currency):
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    if symbol == "€":
        return f"{value:,.2f} {symbol}"
    return f"{symbol}{value:,.2f}"

def fmt_large_number(value, currency):
    if value is None:
        return "—"
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1e9:
        s = f"{value/1e9:.2f}B"
    elif value >= 1e6:
        s = f"{value/1e6:.1f}M"
    else:
        s = f"{value:,.0f}"
    return f"{sign}{symbol}{s}" if symbol != "€" else f"{sign}{s} {symbol}"

def get_fundamentals(ticker):
    info = get_yf_info(ticker)
    return {
        "market_cap": info.get("marketCap"),
        "revenue": info.get("totalRevenue"),
        "net_income": info.get("netIncomeToCommon"),
        "employees": info.get("fullTimeEmployees"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }

# ---------------------------------------------------------------------
# Moteur de calcul
# ---------------------------------------------------------------------
def to_ord(s):
    y, m, d = map(int, s.split("-")); return ddate(y, m, d).toordinal()

def make_so_fn(checkpoints, events):
    cpd = [c[0] for c in checkpoints]
    cpv = [c[1] for c in checkpoints]
    def cum(sd, ed):
        return sum(sh for d, (sh, p) in events.items() if sd < d <= ed)
    def so(date):
        if date <= cpd[0]: return cpv[0]
        if date >= cpd[-1]: return cpv[-1]
        i = bisect.bisect_right(cpd, date) - 1
        d0, d1, v0, v1 = cpd[i], cpd[i+1], cpv[i], cpv[i+1]
        residual = (v1 - v0) - cum(d0, d1)
        t = (to_ord(date) - to_ord(d0)) / (to_ord(d1) - to_ord(d0))
        return v0 + cum(d0, date) + residual * t
    return so

def compute_distribution(ticker, cfg):
    df = None
    last_error = None
    for attempt in range(3):
        try:
            df = yf.download(ticker, start=cfg["start"], auto_adjust=True, progress=False)
            if df is not None and len(df) > 0:
                break
        except Exception as e:
            last_error = e
    if df is None or len(df) == 0:
        raise ValueError(f"Impossible de récupérer les prix pour {ticker}") from last_error
    df = df.reset_index()
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    rows = df.to_dict("records")
    for r in rows:
        r["date"] = r["date"].strftime("%Y-%m-%d")

    # Garde-fou : détecte un saut de prix >55% en un jour (souvent un split mal
    # ajusté ou une rupture de série) et ne garde que l'historique après le
    # dernier saut de ce type, pour éviter une distribution faussée. Filet de
    # sécurité générique -- moins précis que la vérification manuelle faite
    # pour les 14 tickers de référence, mais évite les résultats aberrants
    # sur les autres tickers.
    last_jump_idx = 0
    for idx in range(1, len(rows)):
        prev_close = rows[idx - 1]["close"]
        curr_close = rows[idx]["close"]
        if prev_close and abs(curr_close / prev_close - 1) > 0.55:
            last_jump_idx = idx
    if last_jump_idx > 0 and len(rows) - last_jump_idx >= 40:
        rows = rows[last_jump_idx:]

    so_fn = make_so_fn(cfg["checkpoints"], cfg["events"])
    bucket = cfg["bucket"]
    p_min = min(r["low"] for r in rows)
    def bi(p): return int((p - p_min) / bucket)
    def bp(i): return round(p_min + i * bucket, 4)
    def spread(low, high, qty, acc):
        i_lo, i_hi = bi(low), bi(high)
        if i_hi < i_lo: i_hi = i_lo
        n = i_hi - i_lo + 1
        per = qty / n
        for i in range(i_lo, i_hi + 1): acc[i] = acc.get(i, 0.0) + per

    dist = {}
    spread(rows[0]["low"], rows[0]["high"], so_fn(rows[0]["date"]), dist)
    for r in rows[1:]:
        so = so_fn(r["date"])
        turnover = min(r["volume"] / so, 1.0)
        for i in list(dist.keys()): dist[i] *= (1 - turnover)
        spread(r["low"], r["high"], r["volume"], dist)
        if r["date"] in cfg["events"]:
            sh, p = cfg["events"][r["date"]]
            spread(p, p, sh, dist)

    total = sum(dist.values())
    target = so_fn(rows[-1]["date"])
    dist = {i: v * target / total for i, v in dist.items()}
    total = sum(dist.values())
    return dist, bp, total, rows[-1]["close"], rows[-1]["date"], len(rows), rows

def extended_stats(rows, dist, bp, total, last_close):
    # Range 52 semaines (environ 252 séances de bourse)
    window = rows[-252:] if len(rows) >= 252 else rows
    high_52w = max(r["high"] for r in window)
    low_52w = min(r["low"] for r in window)
    range_position = (last_close - low_52w) / (high_52w - low_52w) * 100 if high_52w > low_52w else 50

    # Variation sur 30 séances
    if len(rows) > 30:
        price_30d_ago = rows[-31]["close"]
        change_30d = (last_close / price_30d_ago - 1) * 100
    else:
        change_30d = None

    # Concentration : part du flottant dans +/-10% du prix actuel
    near = sum(v for i, v in dist.items() if abs(bp(i) - last_close) / last_close <= 0.10)
    concentration_pct = 100 * near / total

    # Zones denses : top 3
    top3 = sorted(dist.items(), key=lambda kv: -kv[1])[:3]
    top3 = [(bp(i), 100 * v / total) for i, v in top3]

    return {
        "high_52w": high_52w, "low_52w": low_52w, "range_position": range_position,
        "change_30d": change_30d, "concentration_pct": concentration_pct, "top3": top3,
    }

# ---------------------------------------------------------------------
# Interface Streamlit
# ---------------------------------------------------------------------
st.set_page_config(page_title="Chip Distribution Explorer", layout="wide", page_icon="◆")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

/* Texture de fond subtile : grille fine façon terminal de trading */
.stApp {
    background-color: #0B1420;
    background-image:
        linear-gradient(rgba(34, 51, 74, 0.35) 1px, transparent 1px),
        linear-gradient(90deg, rgba(34, 51, 74, 0.35) 1px, transparent 1px);
    background-size: 48px 48px;
    background-attachment: fixed;
}

.ticker-header {
    display: flex; align-items: center; gap: 16px;
    padding: 20px 24px; border-radius: 20px;
    background: linear-gradient(135deg, #131F30 0%, #0B1420 100%);
    border: 1px solid #22334A; margin-bottom: 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.ticker-symbol {
    font-family: 'JetBrains Mono', monospace; font-size: 32px; font-weight: 700;
    color: #E8EAED; letter-spacing: 1px;
}
.ticker-price {
    font-family: 'JetBrains Mono', monospace; font-size: 20px; color: #9AA5B1; margin-top: 2px;
}
.badge {
    font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 11.5px;
    padding: 7px 16px; border-radius: 999px; letter-spacing: 0.3px; white-space: nowrap;
}
.badge-gain { background: rgba(46, 160, 90, 0.15); color: #4ADE80; border: 1px solid rgba(74,222,128,0.3); }
.badge-loss { background: rgba(220, 60, 60, 0.15); color: #F87171; border: 1px solid rgba(248,113,113,0.3); }

.stat-card {
    background: linear-gradient(155deg, #17233A 0%, #101A2C 100%);
    border: 1px solid #253652; border-radius: 18px;
    padding: 14px 16px; text-align: left;
    box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}
.stat-label {
    font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #9AA5B1;
    letter-spacing: 1px; margin-bottom: 4px;
}
.stat-value {
    font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; color: #E8EAED;
}

.section-label {
    font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 500;
    color: #7C6CF5; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 6px;
}
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; }

/* Champs de saisie et sélecteurs -- coins arrondis façon app fintech */
.stTextInput>div>div, .stSelectbox>div>div {
    border-radius: 16px !important;
}

.stButton>button,
.stButton>button:hover,
.stButton>button:focus,
.stButton>button:active,
.stButton>button:visited {
    background: linear-gradient(135deg, #8B7CF6 0%, #5B4FE0 100%) !important;
    border: none !important;
    border-radius: 999px !important;
    padding: 12px 26px !important;
    box-shadow: 0 6px 18px rgba(124, 108, 245, 0.35) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton>button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 22px rgba(124, 108, 245, 0.5) !important;
}
.stButton>button p,
.stButton>button div,
.stButton>button span {
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

/* Contenu principal centré mais large, pour ne pas s'étirer sur les très grands écrans */
.block-container { max-width: 1100px; padding-top: 2rem; }
section[data-testid="stSidebar"] { border-right: 1px solid #22334A; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- Détection de la langue du navigateur, pour le libellé par défaut ---
try:
    accept_lang = st.context.headers.get("Accept-Language", "")
except Exception:
    accept_lang = ""
default_index = 1 if accept_lang.lower().startswith("en") else 0

with st.sidebar:
    st.markdown('<div style="font-family:\'JetBrains Mono\',monospace; font-size:11px; color:#7C6CF5; letter-spacing:1px; margin-bottom:6px;">🌐 LANGUE / LANGUAGE</div>', unsafe_allow_html=True)
    lang = st.selectbox(STRINGS["fr"]["lang_selector"], ["Français", "English"], index=default_index, label_visibility="collapsed")
    L = STRINGS["fr"] if lang == "Français" else STRINGS["en"]
    lang_code = "fr" if lang == "Français" else "en"

st.title("◆ " + L["app_title"])
st.caption(L["app_caption"])

raw_input = st.text_input(L["ticker_label"], placeholder=L["ticker_placeholder"], label_visibility="collapsed").strip()

if "resolved_ticker" not in st.session_state:
    st.session_state.resolved_ticker = None
if "name_matches" not in st.session_state:
    st.session_state.name_matches = []
if "last_query" not in st.session_state:
    st.session_state.last_query = ""

if st.button(L["generate_button"]) and raw_input:
    if raw_input.strip().upper() == "YOUSSEF":
        st.session_state.resolved_ticker = None
        st.session_state.name_matches = []
        st.balloons()
        st.markdown(
            '<div style="font-family:\'Space Grotesk\',sans-serif; font-size:28px; font-weight:700; '
            'color:#E8EAED; text-align:center; padding:40px 0;">👋 Salut Abdelklawi Benhmar</div>',
            unsafe_allow_html=True,
        )
        st.stop()

    if raw_input != st.session_state.last_query:
        st.session_state.resolved_ticker = None
        st.session_state.name_matches = []
        st.session_state.last_query = raw_input

    candidate = raw_input.upper()
    if candidate in CURATED:
        st.session_state.resolved_ticker = candidate
    else:
        sec_unreachable = False
        try:
            with st.spinner(L["spinner"].format(ticker=raw_input)):
                cik = get_cik(candidate)
        except Exception:
            cik = None
            sec_unreachable = True
        if cik:
            st.session_state.resolved_ticker = candidate
        elif sec_unreachable:
            st.error(L["error_sec_unreachable"])
        else:
            with st.spinner(L["spinner"].format(ticker=raw_input)):
                matches = search_by_name(raw_input)
            if len(matches) == 1:
                st.session_state.resolved_ticker = matches[0][0]
            elif len(matches) > 1:
                st.session_state.name_matches = matches
            else:
                # dernier essai : peut-être un ticker international valide
                # (Euronext, Tokyo, etc.) que yfinance connaît, même sans
                # correspondance SEC ni nom d'entreprise trouvé
                with st.spinner(L["spinner"].format(ticker=raw_input)):
                    intl_check = get_international_shares(candidate)
                if intl_check:
                    st.session_state.resolved_ticker = candidate
                else:
                    st.error(L["error_not_found"].format(ticker=raw_input))

# --- Désambiguïsation si plusieurs entreprises correspondent au nom tapé ---
if st.session_state.name_matches and not st.session_state.resolved_ticker:
    st.markdown(f'<div class="section-label">{L["multiple_matches"].format(query=st.session_state.last_query)}</div>', unsafe_allow_html=True)
    options = [f"{name} — {ticker}" for ticker, name in st.session_state.name_matches]
    choice = st.selectbox(L["select_placeholder"], options, label_visibility="collapsed")
    if st.button(L["confirm_button"]):
        idx = options.index(choice)
        st.session_state.resolved_ticker = st.session_state.name_matches[idx][0]
        st.session_state.name_matches = []

ticker_input = st.session_state.resolved_ticker

if ticker_input:
    with st.spinner(L["spinner"].format(ticker=ticker_input)):
        if ticker_input in CURATED:
            cfg = CURATED[ticker_input]
            description = cfg["description"][lang_code]
            domain = cfg["domain"]
            currency = cfg["currency"]
            founded = cfg.get("founded")
            listed = cfg.get("listed")
            international_fallback = False
        else:
            try:
                cik = get_cik(ticker_input)
            except Exception:
                st.error(L["error_sec_unreachable"])
                st.stop()
            cps = get_sec_checkpoints(cik) if cik else None
            international_fallback = False
            if not cps:
                cps = get_international_shares(ticker_input)
                international_fallback = cps is not None
            if not cps:
                st.error(L["error_not_found"].format(ticker=ticker_input))
                st.stop()
            start_date = cps[0][0] if not international_fallback else \
                ddate.today().replace(year=ddate.today().year - 10).strftime("%Y-%m-%d")
            cfg = {"start": start_date, "bucket": None, "checkpoints": cps, "events": {}}
            description, website = get_company_description(ticker_input, lang_code)
            domain = urlparse(website).netloc if website else None
            founded, listed = None, None
            currency = get_yf_info(ticker_input).get("currency", "USD")

        fundamentals = get_fundamentals(ticker_input)

        try:
            if cfg["bucket"] is None:
                tmp = yf.download(ticker_input, start=cfg["start"], auto_adjust=True, progress=False)
                price_level = float(tmp["Close"].iloc[-1].iloc[0]) if hasattr(tmp["Close"].iloc[-1], "iloc") else float(tmp["Close"].iloc[-1])
                cfg["bucket"] = max(0.05, round(price_level / 50, 2))

            dist, bp, total, last_close, last_date, n_days, rows = compute_distribution(ticker_input, cfg)
            stats = extended_stats(rows, dist, bp, total, last_close)
        except Exception as e:
            st.error(L["error_compute"].format(err=e))
            st.stop()

    below = sum(v for i, v in dist.items() if bp(i) < last_close)
    pct_gain = 100 * below / total
    pct_loss = 100 - pct_gain
    top_zone = max(dist.items(), key=lambda kv: kv[1])
    top_price = bp(top_zone[0])
    top_pct = 100 * top_zone[1] / total

    # --- En-tête : logo + ticker + prix + badge gain/perte ---
    logo_bytes = fetch_logo_bytes(domain)
    badge_class = "badge-loss" if pct_loss >= pct_gain else "badge-gain"
    badge_text = L["loss_badge"].format(v=pct_loss) if pct_loss >= pct_gain else L["gain_badge"].format(v=pct_gain)

    col1, col2 = st.columns([1, 5])
    with col1:
        if logo_bytes:
            st.image(logo_bytes, width=64)
        else:
            st.markdown('<div style="font-size:40px;">◆</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
            <span class="ticker-symbol">{ticker_input}</span>
            <span class="badge {badge_class}">{badge_text}</span>
        </div>
        <div class="ticker-price">{fmt_currency(last_close, currency)} &nbsp;·&nbsp; {last_date}</div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Rangée de statistiques (52 semaines, tendance) ---
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f'<div class="stat-card"><div class="stat-label">{L["stat_52w_high"]}</div><div class="stat-value">{fmt_currency(stats["high_52w"], currency)}</div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="stat-card"><div class="stat-label">{L["stat_52w_low"]}</div><div class="stat-value">{fmt_currency(stats["low_52w"], currency)}</div></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="stat-card"><div class="stat-label">{L["stat_range_pos"]}</div><div class="stat-value">{stats["range_position"]:.0f}%</div></div>', unsafe_allow_html=True)
    with s4:
        chg = stats["change_30d"]
        chg_color = "#4ADE80" if (chg or 0) >= 0 else "#F87171"
        chg_text = f"{chg:+.1f}%" if chg is not None else "—"
        st.markdown(f'<div class="stat-card"><div class="stat-label">{L["stat_30d"]}</div><div class="stat-value" style="color:{chg_color};">{chg_text}</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if international_fallback:
        st.warning(L["international_note"])

    # --- À propos ---
    if description:
        st.markdown(f'<div class="section-label">{L["about_company"]}</div>', unsafe_allow_html=True)
        st.write(description)
        st.markdown("<br>", unsafe_allow_html=True)

    # --- Fondamentaux : fondation/cotation + chiffres financiers en direct ---
    has_founding_info = founded or listed
    has_financials = any(fundamentals.get(k) for k in ["market_cap", "revenue", "net_income", "sector", "employees"])
    if has_founding_info or has_financials:
        st.markdown(f'<div class="section-label">{L["fundamentals_title"]}</div>', unsafe_allow_html=True)
        f_cols = st.columns(4)
        cards = []
        if founded:
            cards.append((L["founded_label"], str(founded)))
        if listed:
            cards.append((L["listed_label"], listed))
        if fundamentals.get("sector"):
            cards.append((L["sector_label"], fundamentals["sector"]))
        if fundamentals.get("employees"):
            cards.append((L["employees_label"], f"{fundamentals['employees']:,}"))
        if fundamentals.get("market_cap"):
            cards.append((L["market_cap_label"], fmt_large_number(fundamentals["market_cap"], currency)))
        if fundamentals.get("revenue"):
            cards.append((L["revenue_label"], fmt_large_number(fundamentals["revenue"], currency)))
        if fundamentals.get("net_income"):
            ni = fundamentals["net_income"]
            ni_color = "#4ADE80" if ni >= 0 else "#F87171"
            cards.append((L["net_income_label"], fmt_large_number(ni, currency), ni_color))
        for idx, card in enumerate(cards):
            label, value = card[0], card[1]
            color = card[2] if len(card) > 2 else "#E8EAED"
            with f_cols[idx % 4]:
                st.markdown(
                    f'<div class="stat-card" style="margin-bottom:10px;">'
                    f'<div class="stat-label">{label}</div>'
                    f'<div class="stat-value" style="font-size:15px; color:{color};">{value}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

    # --- Analyse (résumé + interprétation + statistiques enrichies) ---
    if abs(top_price - last_close) / last_close < 0.05:
        position = L["position_center"]
    elif top_price > last_close:
        position = L["position_above"].format(pct=100*(top_price/last_close-1))
    else:
        position = L["position_below"].format(pct=100*(1-top_price/last_close))
    gain_perte_txt = L["majority_loss"] if pct_loss > 55 else (L["majority_gain"] if pct_gain > 55 else L["balanced"])

    chg = stats["change_30d"]
    if chg is None:
        trend_txt = ""
    elif chg > 2:
        trend_txt = L["trend_up"].format(v=chg)
    elif chg < -2:
        trend_txt = L["trend_down"].format(v=chg)
    else:
        trend_txt = L["trend_flat"].format(v=chg)

    concentration_txt = L["concentration_high"] if stats["concentration_pct"] > 40 else L["concentration_low"]

    secondary_txt = ""
    if len(stats["top3"]) > 1:
        second_price, second_pct = stats["top3"][1]
        if second_pct > 3 and abs(second_price - top_price) / top_price > 0.05:
            secondary_txt = L["secondary_zone"].format(price=second_price, pct=second_pct)

    st.markdown(f'<div class="section-label">{L["analysis_title"]}</div>', unsafe_allow_html=True)
    st.write(L["analysis_text"].format(date=last_date, price=last_close, gain=pct_gain, loss=pct_loss,
                                        top_price=top_price, top_pct=top_pct, position=position, gain_perte_txt=gain_perte_txt))
    st.write(L["analysis_extended"].format(
        low=stats["low_52w"], high=stats["high_52w"], range_pos=stats["range_position"],
        trend_txt=trend_txt, concentration=stats["concentration_pct"], concentration_txt=concentration_txt,
        secondary_txt=secondary_txt,
    ))
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Distribution (prix actuel affiché à gauche, en dehors du graphique) ---
    st.markdown(f'<div class="section-label">{L["distribution_title"]}</div>', unsafe_allow_html=True)
    MAX_BARS = 28
    EMPTY_THRESHOLD = 0.05  # % -- en dessous, un tiroir est considéré vide et zappé

    # 1) Regroupement fin (résolution native du modèle)
    fine = {}
    for i, v in dist.items():
        key = bp(i)
        fine[key] = fine.get(key, 0) + v
    fine_items = sorted(fine.items())

    # 2) Regroupement adaptatif : on élargit la taille des tiroirs jusqu'à ce que
    #    le nombre de tiroirs NON VIDES tienne dans MAX_BARS -- un tiroir isolé
    #    loin du prix actuel reste affiché tant qu'il contient une masse réelle.
    coarse = cfg["bucket"]
    while True:
        buckets = {}
        for p, v in fine_items:
            key = round((p // coarse) * coarse, 2)
            buckets[key] = buckets.get(key, 0) + v
        non_empty = {k: v for k, v in buckets.items() if 100 * v / total >= EMPTY_THRESHOLD}
        if len(non_empty) <= MAX_BARS or coarse > (fine_items[-1][0] - fine_items[0][0]):
            break
        coarse *= 1.6

    items = sorted(non_empty.items())
    prices = [k for k, v in items]
    pcts = [100 * v / total for k, v in items]
    shown_mass_pct = sum(pcts)
    colors = ["#F87171" if p + coarse/2 > last_close else "#4ADE80" for p in prices]
    y_pos = list(range(len(prices)))  # position catégorielle : chaque tiroir = un cran égal

    # position (fractionnaire) du prix actuel dans cet axe catégoriel, par interpolation
    if last_close <= prices[0]:
        price_y = 0.0
    elif last_close >= prices[-1]:
        price_y = float(len(prices) - 1)
    else:
        j = 0
        while j < len(prices) - 1 and prices[j+1] < last_close:
            j += 1
        span = (prices[j+1] - prices[j]) or 1
        price_y = j + (last_close - prices[j]) / span

    price_col, chart_col = st.columns([1, 4])
    with price_col:
        st.markdown(f"""
        <div style="background:linear-gradient(155deg, #17233A 0%, #101A2C 100%); border:1px solid #253652; border-radius:18px; padding:16px; margin-top:40px; box-shadow:0 4px 14px rgba(0,0,0,0.18);">
            <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#7C6CF5; letter-spacing:1px;">{L["price_box_label"]}</div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:24px; font-weight:700; color:#E8EAED; margin-top:4px;">{fmt_currency(last_close, currency)}</div>
        </div>
        """, unsafe_allow_html=True)

    with chart_col:
        plt.rcParams["font.family"] = "sans-serif"
        fig, ax = plt.subplots(figsize=(7, min(11, max(4, len(items)*0.34))))
        fig.patch.set_facecolor("#0B1420")
        ax.set_facecolor("#0B1420")
        bars = ax.barh(y_pos, pcts, height=0.68, color=colors, zorder=2)
        for bar, pct in zip(bars, pcts):
            if pct > 0.15:
                ax.text(bar.get_width() + max(pcts)*0.02, bar.get_y() + bar.get_height()/2,
                        f"{pct:.1f}%", va="center", fontsize=8, fontweight="bold", color="#E8EAED", zorder=4)

        # Grille discrète façon terminal de trading
        ax.grid(axis="x", color="#22334A", linewidth=0.6, alpha=0.6, zorder=0)
        ax.set_axisbelow(True)

        # Ligne de prix actuel (position interpolée sur l'axe catégoriel) + étiquette prix
        ax.axhline(price_y, color="#7C6CF5", linestyle="--", linewidth=1.5, zorder=3)
        ax.annotate(
            fmt_currency(last_close, currency),
            xy=(1.0, price_y), xycoords=("axes fraction", "data"),
            xytext=(10, 0), textcoords="offset points",
            va="center", ha="left", fontsize=10, fontweight="bold", color="#0B1420",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#7C6CF5", edgecolor="none"),
            annotation_clip=False, zorder=5,
        )

        # Axe des prix avec devise, axe des % avec symbole
        ax.set_yticks(y_pos)
        ax.set_yticklabels([fmt_currency(p, currency) for p in prices], fontsize=8)
        ax.set_ylim(-0.6, len(prices) - 0.4)
        ax.xaxis.set_major_formatter(lambda x, pos: f"{x:.0f}%")
        ax.set_xlabel(L["chart_xlabel"], color="#9AA5B1")
        ax.set_title(L["chart_title"].format(n=n_days), color="#E8EAED", fontsize=11, loc="left")
        if shown_mass_pct < 99.4:
            ax.text(0, 1.06, L["chart_trimmed_note"].format(pct=shown_mass_pct), transform=ax.transAxes,
                    fontsize=8.5, color="#9AA5B1", style="italic")
        ax.set_xlim(0, max(pcts) * 1.2)
        ax.tick_params(colors="#9AA5B1")
        for spine in ax.spines.values():
            spine.set_color("#22334A")
        fig.subplots_adjust(right=0.86)
        st.pyplot(fig)

    st.caption(L["disclaimer"])
