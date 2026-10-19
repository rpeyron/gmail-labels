#!/usr/bin/env python3
"""Check message headers and text bodies for encoding problems in an mbox/sbd tree."""

from __future__ import annotations

import argparse
import codecs
import html
import mailbox
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from email import policy
from email.header import decode_header
from email.headerregistry import Address
from email.message import EmailMessage
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterator


MOJIBAKE_PATTERN = re.compile(
    r"(?:Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|"
    r"â(?:€|‚|ƒ|„|…|†|‡|ˆ|‰|Š|‹|Œ|Ž|‘|’|“|”|•|–|—|˜|™|š|›|œ|ž|Ÿ)|"
    r"ðŸ[\u0080-\u00bf]{2}|ï»¿)"
)
IGNORED_SUFFIXES = {".html", ".log", ".msf"}
SNIPPET_LIMIT = 120
HTML_CHARSET_PATTERN = re.compile(
    rb"<meta\b[^>]*?\bcharset\s*=\s*[\"']?\s*([a-zA-Z0-9._-]+)",
    re.IGNORECASE,
)
HTML_CHARSET_TEXT_PATTERN = re.compile(
    r"(<meta\b[^>]*?\bcharset\s*=\s*[\"']?\s*)"
    r"([a-zA-Z0-9._-]+)",
    re.IGNORECASE,
)
PLAIN_HTML_TAG_PATTERN = re.compile(
    r"</?(?:a|br|blockquote|div|em|font|h[1-6]|img|li|ol|p|span|strong|table|"
    r"tbody|td|th|tr|ul)\b[^>]*>",
    re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"(?:[^\W_]|\ufffd)+", re.UNICODE)
BYTE_ORDER_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
    (codecs.BOM_UTF8, "utf-8-sig"),
)
CONTEXTUAL_REPLACEMENTS = {
    "l\ufffdensemble": "l'ensemble",
    "r\ufffd\ufffdseau": "r\u00e9seau",
    "vous pouvez vous d\ufffd\ufffdsinscrire": "vous pouvez vous d\u00e9sinscrire",
    "aujourd\ufffd\ufffd\ufffdhui": "aujourd'hui",
    "l\ufffd\ufffd\ufffdappli": "l'appli",
    "s\ufffd\ufffdlectionn\ufffd\ufffdes": "s\u00e9lectionn\u00e9es",
    "d\ufffd\ufffd\ufffdadresse": "d'adresse",
    "l\ufffd\ufffd\ufffdoffre": "l'offre",
    "l\ufffd\ufffd\ufffdactu": "l'actu",
    "\ufffd\ufffd         ": "\u2022         ",
    "votre r\ufffd\ufffdseau partout avec vous avec l\ufffd\ufffd\ufffdappli": (
        "votre r\u00e9seau partout avec vous avec l'appli"
    ),
    "etendez votre r\ufffd\ufffdseau avec les personnes que nous avons "
    "s\ufffd\ufffdlectionn\ufffd\ufffdes": (
        "etendez votre r\u00e9seau avec les personnes que nous avons "
        "s\u00e9lectionn\u00e9es"
    ),
    "vos anciens coll\ufffd\ufffdgues": "vos anciens coll\u00e8gues",
    "importez votre carnet d\ufffd\ufffd\ufffdadresse": (
        "importez votre carnet d'adresse"
    ),
    "voir l\ufffd\ufffd\ufffdoffre premium": "voir l'offre premium",
    "voir toute l\ufffd\ufffd\ufffdactu de mes contacts": (
        "voir toute l'actu de mes contacts"
    ),
    "votre profil consult\ufffd\ufffd": "votre profil consult\u00e9",
    "compl\ufffd\ufffdtez votre profil": "compl\u00e9tez votre profil",
    "aur\ufffd\ufffdlie gaucher": "aur\u00e9lie gaucher",
    "st\ufffd\ufffdphane rodier": "st\u00e9phane rodier",
    "de vos contacts ont ajout\ufffd\ufffd": "de vos contacts ont ajout\u00e9",
    "des comp\ufffd\ufffdtences recherch\ufffd\ufffds par leur secteur": (
        "des comp\u00e9tences recherch\u00e9s par leur secteur"
    ),
    "moyenne constat\ufffd\ufffde sur les membres premium": (
        "moyenne constat\u00e9e sur les membres premium"
    ),
    "d\ufffd\ufffdcouvrez": "d\u00e9couvrez",
    "r\ufffdmi": "r\u00e9mi",
    "votre profil int\ufffd\ufffdresse": "votre profil int\u00e9resse",
    "vous avez acc\ufffd\ufffds": "vous avez acc\u00e8s",
    "vous avez acc\u00e8s \ufffd\ufffd tous les profils": (
        "vous avez acc\u00e8s \u00e0 tous les profils"
    ),
    " \ufffd\ufffd tous les profils": " \u00e0 tous les profils",
    "acc\u00e8s \ufffd\ufffd tous les profils": (
        "acc\u00e8s \u00e0 tous les profils"
    ),
    "R\ufffdMI": "R\u00c9MI",
    "T\ufffdl\ufffdchargez": "T\u00e9l\u00e9chargez",
    "sant\ufffd": "sant\u00e9",
    "f\ufffdri\ufffds": "f\u00e9ri\u00e9s",
    "mod\ufffdration": "mod\u00e9ration",
    "alcoolis\ufffdes": "alcoolis\u00e9es",
    "m\ufffdme": "m\u00eame",
    "quantit\ufffd": "quantit\u00e9",
    "cons\ufffdquences": "cons\u00e9quences",
    "s\ufffdlection": "s\u00e9lection",
    "personnalis\ufffde": "personnalis\u00e9e",
    "\ufffd l'attention des clients soci\u00e9taires": (
        "\u00c0 l'attention des clients soci\u00e9taires"
    ),
    "\ufffd l'Assembl\u00e9e G\u00e9n\u00e9rale": "\u00e0 l'Assembl\u00e9e G\u00e9n\u00e9rale",
    "invitons \ufffd la lire": "invitons \u00e0 la lire",
    "r\u00e9pondre \ufffd ces": "r\u00e9pondre \u00e0 ces",
    "rencontrer \ufffd l'occasion": "rencontrer \u00e0 l'occasion",
    "cet \ufffdv\u00e9nement": "cet \u00e9v\u00e9nement",
    "coop\u00e9rative \ufffd capital variable": (
        "coop\u00e9rative \u00e0 capital variable"
    ),
    "\ufffd capital variable": "\u00e0 capital variable",
    "D\u00c9TAILL\u00c9E \ufffdAVEC": "D\u00c9TAILL\u00c9E AVEC",
    "R\u00c9MI, \ufffd la recherche": "R\u00c9MI, \u00e0 la recherche",
    "type=\ufffdtext/css\ufffd": 'type="text/css"',
    "Vid\ufffdoprojecteur": "Vid\u00e9oprojecteur",
    "Po\ufffdle \ufffd p\ufffdtrole \ufffdlectronique": (
        "Po\u00eale \u00e0 p\u00e9trole \u00e9lectronique"
    ),
    "Po\ufffdle \ufffd gaz": "Po\u00eale \u00e0 gaz",
    "Radiateur c\ufffdramique": "Radiateur c\u00e9ramique",
    "Radiateurs \ufffdlectriques \ufffd inertie": (
        "Radiateurs \u00e9lectriques \u00e0 inertie"
    ),
    "tous les promos \ufffd ne pas rater": "tous les promos \u00e0 ne pas rater",
    "vendre ou offrir \ufffd des mineurs": "vendre ou offrir \u00e0 des mineurs",
    "\ufffd consommer avec mod\u00e9ration": "\u00e0 consommer avec mod\u00e9ration",
    "V\ufffdlos": "V\u00e9los",
    "D\ufffdj\ufffd": "D\u00e9j\u00e0",
    "sport connect\ufffd": "sport connect\u00e9",
    "id\ufffdes cadeaux": "id\u00e9es cadeaux",
    "privil\ufffdges": "privil\u00e8ges",
    "facilit\ufffds de paiement": "facilit\u00e9s de paiement",
    "s\ufffdcurit\ufffd": "s\u00e9curit\u00e9",
    "s\ufffd\ufffdcurit\ufffd\ufffd": "s\u00e9curit\u00e9",
    "r\ufffdalit\ufffd": "r\u00e9alit\u00e9",
    "int\ufffdr\ufffdt": "int\u00e9r\u00eat",
    "\ufffdcrit": "\u00e9crit",
    "v\ufffdlo": "v\u00e9lo",
    "polaris\ufffdes": "polaris\u00e9es",
    "r\ufffdunion": "r\u00e9union",
    "pr\ufffdsentation": "pr\u00e9sentation",
    "etant donn\ufffd": "\u00e9tant donn\u00e9",
    "fran\ufffdois": "fran\u00e7ois",
    "abord\ufffds": "abord\u00e9s",
    "pr\ufffdsents": "pr\u00e9sents",
    "int\ufffdress\ufffd": "int\u00e9ress\u00e9",
    "int\ufffdress\ufffds": "int\u00e9ress\u00e9s",
    "r\ufffdalisation": "r\u00e9alisation",
    "mod\ufffdlisation": "mod\u00e9lisation",
    "diff\ufffdrentes": "diff\u00e9rentes",
    "\ufffdtaient": "\u00e9taient",
    "derni\ufffdre": "derni\u00e8re",
    "\ufffdtre": "\u00eatre",
    "d\ufffdroulent": "d\u00e9roulent",
    "id\ufffdes cit\ufffdes": "id\u00e9es cit\u00e9es",
    "rentr\ufffdes": "rentr\u00e9es",
    "g\ufffdn\ufffdr\ufffds": "g\u00e9n\u00e9r\u00e9s",
    "destin\ufffdes": "destin\u00e9es",
    "profil\ufffds": "profil\u00e9s",
    "treillis soud\ufffds": "treillis soud\u00e9s",
    "produits semi-finis en m\ufffdtal": "produits semi-finis en m\u00e9tal",
    "b\ufffdchenbeuren": "b\u00fcchenbeuren",
    "t\ufffdl\ufffdphone": "t\u00e9l\u00e9phone",
    "enregistrement l\ufffdgal": "enregistrement l\u00e9gal",
    "cr\ufffddit agricole": "cr\u00e9dit agricole",
    "n\ufffd tva": "n\u00b0 tva",
    "cr\ufffddit\ufffd": "cr\u00e9dit\u00e9",
    "proc\ufffdd\ufffd \ufffd un remboursement": (
        "proc\u00e9d\u00e9 \u00e0 un remboursement"
    ),
    "nous tenons \ufffd vous remercier": "nous tenons \u00e0 vous remercier",
    "r\ufffdpondu \ufffd toutes vos attentes": (
        "r\u00e9pondu \u00e0 toutes vos attentes"
    ),
    "toute information compl\ufffdmentaire": "toute information compl\u00e9mentaire",
    "ch\ufffdre cliente": "ch\u00e8re cliente",
    "nos sinc\ufffdres salutations": "nos sinc\u00e8res salutations",
    "remboursement aura \ufffdt\ufffd trait\ufffd": (
        "remboursement aura \u00e9t\u00e9 trait\u00e9"
    ),
    "sera revers\ufffd sur le compte associ\ufffd \ufffd votre m\ufffdthode": (
        "sera revers\u00e9 sur le compte associ\u00e9 \u00e0 votre m\u00e9thode"
    ),
    "message vous a \ufffdt\ufffd envoy\ufffd": (
        "message vous a \u00e9t\u00e9 envoy\u00e9"
    ),
    "apr\ufffds v\ufffdrification": "apr\u00e8s v\u00e9rification",
    "d\ufffdj\ufffd \ufffdt\ufffd trait\ufffd": "d\u00e9j\u00e0 \u00e9t\u00e9 trait\u00e9",
    "en esp\ufffdrant": "en esp\u00e9rant",
    "derni\ufffdre demande": "derni\u00e8re demande",
    "\ufffd votre enti\ufffdre disposition": "\u00e0 votre enti\u00e8re disposition",
    "compl\ufffdmentaire": "compl\u00e9mentaire",
    "ch\ufffdre cliente": "ch\u00e8re cliente",
    "coll\ufffdgues \ufffd se connecter": "coll\u00e8gues \u00e0 se connecter",
    "communications ponctuelles destin\ufffdes \ufffd vous": (
        "communications ponctuelles destin\u00e9es \u00e0 vous"
    ),
    "alain thiebat - \ufffdchouer rapidement": (
        "alain thiebat - \u00e9chouer rapidement"
    ),
    "au plus t\ufffdt": "au plus t\u00f4t",
    "\ufffd partir": "\u00e0 partir",
    "commencera \ufffd 18h00": "commencera \u00e0 18H00",
    "\ufffdvolution de la r\ufffdglementation": (
        "\u00e9volution de la r\u00e9glementation"
    ),
    "face \ufffd ces d\ufffdfis": "face \u00e0 ces d\u00e9fis",
    "\ufffdgalement poser une question": "\u00e9galement poser une question",
    "\ufffdtant effectu\ufffd par moyen \ufffdlectronique": (
        "\u00e9tant effectu\u00e9 par moyen \u00e9lectronique"
    ),
    "\ufffdshutterstock": "\u00a9Shutterstock",
    "vous trouverez ci-dessous votre re\ufffdu de paiement \ufffd conserver": (
        "vous trouverez ci-dessous votre re\u00e7u de paiement \u00e0 conserver"
    ),
    "0.15\ufffd/min": "0.15\u20ac/min",
    "capital de 1.000.000 \ufffd": "capital de 1.000.000 \u20ac",
    "ampoulea\ufffd d\ufffdclenchement": "ampoule \u00e0 d\u00e9clenchement",
    "t\ufffdl. ": "t\u00e9l. ",
    "marie-c\ufffdcile": "marie-c\u00e9cile",
    "\ufffdtre acteur de r\ufffdf\ufffdrence": (
        "\u00eatre acteur de r\u00e9f\u00e9rence"
    ),
    "accueil \ufffd partir de 17h30": "accueil \u00e0 partir de 17H30",
    "la strat\ufffdgie de votre banque, face \ufffd ces d\ufffdfis": (
        "la strat\u00e9gie de votre banque, face \u00e0 ces d\u00e9fis"
    ),
    "soci\ufffdt\ufffd coop\ufffdrative \ufffd capital variable": (
        "soci\u00e9t\u00e9 coop\u00e9rative \u00e0 capital variable"
    ),
    "cr\ufffddits photos : \ufffdshutterstock": (
        "cr\u00e9dits photos : \u00a9Shutterstock"
    ),
    "remember \ufffd your contribution is anonymous": (
        "remember \u2014 your contribution is anonymous"
    ),
    "you\ufffdre the only one with your job title": (
        "you're the only one with your job title"
    ),
    "a \ufffdt\ufffd remis en place": "a \u00e9t\u00e9 remis en place",
    "r\ufffdpertoire": "r\u00e9pertoire",
    "associ\ufffd": "associ\u00e9",
    "mont\ufffd sur zen": "mont\u00e9 sur zen",
    "l'acc\ufffds": "l'acc\u00e8s",
    "est \ufffdgalement remis en place": "est \u00e9galement remis en place",
    "recevez, ch\ufffdre cliente": "recevez, ch\u00e8re cliente",
    "l'application digiposte, retrouvez, d\ufffds aujourd'hui": (
        "l'application digiposte, retrouvez, d\u00e8s aujourd'hui"
    ),
    "documents stock\ufffds dans \ufffd\ufffdvotre coffre": (
        "documents stock\u00e9s dans votre coffre"
    ),
    "dans\n\ufffd\ufffdvotre coffre": "dans\nvotre coffre",
    "conservez-les \ufffd\ufffddans votre coffre": (
        "conservez-les dans votre coffre"
    ),
    "conservez-les\n\ufffd\ufffddans votre coffre": (
        "conservez-les\ndans votre coffre"
    ),
    "gr\ufffdce \ufffd l'application digiposte": (
        "gr\u00e2ce \u00e0 l'application digiposte"
    ),
    "acc\ufffddez \ufffd vos documents importants": (
        "acc\u00e9dez \u00e0 vos documents importants"
    ),
    "e-mail \ufffd l'adresse": "e-mail \u00e0 l'adresse",
    "copropri\ufffd\ufffdt": "copropri\u00e9t\u00e9",
    "\u00e0 300 \ufffd": "\u00e0 300 \u20ac",    "r\ufffdpons": "r\u00e9ponse",
    "\ufffdvolution": "\u00e9volution",
    "\ufffdgalement": "\u00e9galement",
    "\ufffdtant": "\u00e9tant",
    "\ufffdlectronique": "\u00e9lectronique",
    "ou\ufffd": "o\u00f9",
    "\ufffdquipement": "\u00e9quipement",
    "fa\ufffdons": "fa\u00e7ons",
    "pr\ufffdsente": "pr\u00e9sente",
    "tha\ufffdlande": "tha\u00eflande",
    "g\ufffdn\ufffdral": "g\u00e9n\u00e9ral",
    "liquidit\ufffd": "liquidit\u00e9",
    "dur\ufffde": "dur\u00e9e",
    "oblig\ufffd": "oblig\u00e9",
    "retard\ufffd": "retard\u00e9",
    "co\ufffdte": "co\u00fbte",
    "achet\ufffds": "achet\u00e9s",
    "\ufffdviter": "\u00e9viter",
    "su\ufffdde": "su\u00e8de",
    "attir\ufffd": "attir\u00e9",
    "flexibilit\ufffd": "flexibilit\u00e9",
    "\ufffdtudie": "\u00e9tudie",
    "cr\ufffd\ufffds": "cr\u00e9\u00e9s",
    "coh\ufffdrence": "coh\u00e9rence",
    "donn\ufffde": "donn\u00e9e",
    "premi\ufffdre": "premi\u00e8re",
    "m\ufffdcanique": "m\u00e9canique",
    "journ\ufffde": "journ\u00e9e",
    "thal\ufffds": "thal\u00e8s",
    "\ufffdtudiants": "\u00e9tudiants",
    "rencontr\ufffde": "rencontr\u00e9e",
    "d\ufffds": "d\u00e8s",
    "d\ufffdtail": "d\u00e9tail",
    "fran\ufffdaises": "fran\u00e7aises",
    "coordonn\ufffdes": "coordonn\u00e9es",
    "activit\ufffd": "activit\u00e9",
    "multicrit\ufffdres": "multicrit\u00e8res",
    "d\ufffdpartement": "d\u00e9partement",
    "illimit\ufffdes": "illimit\u00e9es",
    "\ufffdtiquettes": "\u00e9tiquettes",
    "fonctionnalit\ufffd": "fonctionnalit\u00e9",
    "\ufffddit\ufffd": "\u00e9dit\u00e9",
    "si\ufffdges": "si\u00e8ges",
    "\ufffdtablissements": "\u00e9tablissements",
    "priv\ufffd": "priv\u00e9",
    "visit\ufffd": "visit\u00e9",
    "organis\ufffd": "organis\u00e9",
    "d\ufffdsabonner": "d\u00e9sabonner",
    "399\ufffd": "399\u20ac",
    "199\ufffd": "199\u20ac",
    "aupr\ufffds": "aupr\u00e8s",
    "r\ufffdpondre": "r\u00e9pondre",
    "ge\ufffdffnet": "ge\u00f6ffnet",
    "\ufffd tout moment": "\u00e0 tout moment",
    "gr\ufffdce \ufffd l'application": "gr\u00e2ce \u00e0 l'application",
    "acc\ufffdder \ufffd": "acc\u00e9der \u00e0",
    "dans \ufffd\ufffdvotre coffre": "dans votre coffre",
    "conservez-les \ufffd\ufffddans": "conservez-les dans",
    "google analytics \ufffd google inc.": (
        "google analytics \u00a9 google inc."
    ),
    "l'acc\ufffds via http": "l'acc\u00e8s via http",
    "convocation \ufffd votre assembl\ufffde": (
        "convocation \u00e0 votre assembl\u00e9e"
    ),
    "accueil \ufffd partir": "accueil \u00e0 partir",
    "l'assembl\ufffde g\ufffdn\ufffdrale commencera": (
        "l'assembl\u00e9e g\u00e9n\u00e9rale commencera"
    ),
    "int\ufffdr\ufffdts du march\ufffd": "int\u00e9r\u00eats du march\u00e9",
    "\ufffdvolution de la r\ufffdglementation": (
        "\u00e9volution de la r\u00e9glementation"
    ),
    "la poste vous a envoy\ufffd cet e-mail \ufffd l'adresse": (
        "la poste vous a envoy\u00e9 cet e-mail \u00e0 l'adresse"
    ),
    "re\ufffdu de paiement \ufffd conserver": (
        "re\u00e7u de paiement \u00e0 conserver"
    ),
    "fringues \ufffd jeter": "fringues \u00e0 jeter",
    "la tha\u00eflande, \ufffda allait": "la Tha\u00eflande, \u00e7a allait",
    "de 4 \ufffd 10 euros": "de 4 \u00e0 10 euros",
    "structures \ufffd en fournir": "structures \u00e0 en fournir",
    "\ufffda fait tard": "\u00e7a fait tard",
    "cet \ufffdt\ufffd en inde": "cet \u00e9t\u00e9 en Inde",
    "pour l'\ufffdt\ufffd dernier": "pour l'\u00e9t\u00e9 dernier",
    "l'\ufffdt\ufffd dernier": "l'\u00e9t\u00e9 dernier",
    "qu'on \ufffdtait": "qu'on \u00e9tait",
    "poil \ufffd l'arrache": "poil \u00e0 l'arrache",
    "mal \ufffd trouver": "mal \u00e0 trouver",
    "billets ont \ufffdt\ufffd achet\ufffds": "billets ont \u00e9t\u00e9 achet\u00e9s",
    "sp\ufffdcialement envie": "sp\u00e9cialement envie",
    "750 \ufffd 800 euros": "750 \u00e0 800 euros",
    "taxes a\ufffdriennes": "taxes a\u00e9riennes",
    "vols int\ufffdrieurs": "vols int\u00e9rieurs",
    "pas encore pr\ufffdt": "pas encore pr\u00eat",
    "j'ai v\ufffdrif\ufffd en regardant": "j'ai v\u00e9rifi\u00e9 en regardant",
    "trouv\ufffd des le\ufffdons": "trouv\u00e9 des le\u00e7ons",
    "rthk.org \ufffd base": "rthk.org \u00e0 base",
    "mais \ufffda timeoute lamentablement": (
        "mais \u00e7a timeoute lamentablement"
    ),
    "programme \ufffd structure complexe": (
        "programme \u00e0 structure complexe"
    ),
    "pr\ufffdsents \ufffd la derni\ufffdre": (
        "pr\u00e9sents \u00e0 la derni\u00e8re"
    ),
    "mettre \ufffd jour": "mettre \u00e0 jour",
    "auront \ufffdt\ufffd cr\ufffd\ufffds": "auront \u00e9t\u00e9 cr\u00e9\u00e9s",
    "destin\ufffdes \ufffd la visualisation": (
        "destin\u00e9es \u00e0 la visualisation"
    ),
    "a \ufffdt\ufffd rencontr\ufffde": "a \u00e9t\u00e9 rencontr\u00e9e",
    "mat\ufffdriel": "mat\u00e9riel",
    "mati\ufffdre": "mati\u00e8re",
    "temps r\ufffdel": "temps r\u00e9el",
    "sp\ufffdcialiste": "sp\u00e9cialiste",
    "t\ufffdtes": "t\u00eates",
    "travaille \ufffd la restauration": "travaille \u00e0 la restauration",
    "m\ufffdthodes": "m\u00e9thodes",
    "\ufffdcoles": "\u00e9coles",
    "contact\ufffdes": "contact\u00e9es",
    "justifi\ufffde": "justifi\u00e9e",
    "demande \ufffd faire": "demande \u00e0 faire",
    " \ufffd faire": " \u00e0 faire",
    "un \ufffdventuel": "un \u00e9ventuel",
    "achat de mat\ufffdriel \ufffd simteam": (
        "achat de mat\u00e9riel \u00e0 Simteam"
    ),
    "\ufffdcrire un article": "\u00e9crire un article",
    "d\ufffdveloppement": "d\u00e9veloppement",
    "facilit\ufffd d'utilisation": "facilit\u00e9 d'utilisation",
    "\ufffd plus long temps de calcul": "\u00e0 plus long temps de calcul",
    "o\ufffd mettre les contacts": "o\u00f9 mettre les contacts",
    "sera utilis\ufffd pour le rapport": "sera utilis\u00e9 pour le rapport",
    "penser \ufffdventuellement \ufffd kyle": (
        "penser \u00e9ventuellement \u00e0 Kyle"
    ),
    "interface \ufffd latek": "interface \u00e0 Latek",
    "n\ufffd de t\ufffdl.": "n\u00b0 de t\u00e9l.",
    "n\ufffd de": "n\u00b0 de",
    "1\ufffdre messagerie": "1\u00e8re messagerie",
    "instantan\ufffde": "instantan\u00e9e",
    "t\ufffdl\ufffdcharger msn messenger": "t\u00e9l\u00e9charger MSN Messenger",
    "n\ufffd fiscal": "n\u00b0 fiscal",
    "coll\ufffdgues \ufffd se connecter": "coll\u00e8gues \u00e0 se connecter",
    "image \ufffd 2011 linkedin corporation": (
        "image \u00a9 2011 LinkedIn Corporation"
    ),
    "alain thiebat \ufffdchouer rapidement": (
        "Alain Thiebat \u00e9chouer rapidement"
    ),
    "n'a pas \ufffdt\ufffd envoy\ufffd \ufffd son destinataire": (
        "n'a pas \u00e9t\u00e9 envoy\u00e9 \u00e0 son destinataire"
    ),
    "s'am\ufffdliore gr\ufffdce \ufffd vous": (
        "s'am\u00e9liore gr\u00e2ce \u00e0 vous"
    ),
    "a d\ufffdj\ufffd \ufffdt\ufffd trait\ufffd": (
        "a d\u00e9j\u00e0 \u00e9t\u00e9 trait\u00e9"
    ),
    "mise \ufffd disposition de vos documents": (
        "mise \u00e0 disposition de vos documents"
    ),
    "analytics \ufffd\u00a0google\u00a0inc.": (
        "Analytics \u00a9\u00a0Google\u00a0Inc."
    ),
    "acc\ufffds en lecture": "acc\u00e8s en lecture",
    "249\ufffd": "249\u20ac",
    "199\ufffd": "199\u20ac",
    "254\ufffd": "254\u20ac",
    "q\ufffd la caisse": "q\u00e0 la caisse",
    "\ufffda allait de": "\u00e7a allait de",
    "\ufffda vaut le coup": "\u00e7a vaut le coup",
    "auront \ufffdt\ufffd": "auront \u00e9t\u00e9",
    "auraient port\ufffd": "auraient port\u00e9",
    "!!!\ufffd\ufffd\ufffd\ufffd": "!!!",
    'font-family:&quot;Tahoma&quot;,sans-serif">\ufffd\ufffd\ufffd\ufffd</span>': (
        'font-family:&quot;Tahoma&quot;,sans-serif"></span>'
    ),
    "re\u00e7u de paiement \ufffd conserver": (
        "re\u00e7u de paiement \u00e0 conserver"
    ),
    "convocation \ufffd votre assembl\u00e9e": (
        "convocation \u00e0 votre assembl\u00e9e"
    ),
    "l\ufffd-bas": "l\u00e0-bas",
    "en g\u00e9n\u00e9ral, \ufffda vaut le coup": (
        "en g\u00e9n\u00e9ral, \u00e7a vaut le coup"
    ),
    "poil \ufffd\nl'arrache": "poil \u00e0\nl'arrache",
    "billets ont \ufffdt\ufffd achet\u00e9s": (
        "billets ont \u00e9t\u00e9 achet\u00e9s"
    ),
    "programme \ufffd \nstructure complexe": (
        "programme \u00e0 \nstructure complexe"
    ),
    "pr\u00e9sents \ufffd la derni\u00e8re": (
        "pr\u00e9sents \u00e0 la derni\u00e8re"
    ),
    "auront \ufffdt\ufffd \ncr\u00e9\u00e9s": (
        "auront \u00e9t\u00e9 \ncr\u00e9\u00e9s"
    ),
    "t\ufffdl.": "t\u00e9l.",
    "249 \ufffd": "249 \u20ac",
    "199 \ufffd": "199 \u20ac",
    "254 \ufffd": "254 \u20ac",
    "coll\u00e8gues \ufffd se connecter": (
        "coll\u00e8gues \u00e0 se connecter"
    ),
    "image \n\n\ufffd 2011 linkedin corporation": (
        "image \n\n\u00a9 2011 LinkedIn Corporation"
    ),
    "destin\u00e9es \ufffd vous": "destin\u00e9es \u00e0 vous",
    "</a> \ufffdchouer rapidement": "</a> \u00e9chouer rapidement",
    "n'a pas \ufffdt\u00e9 envoy\u00e9 \ufffd son destinataire": (
        "n'a pas \u00e9t\u00e9 envoy\u00e9 \u00e0 son destinataire"
    ),
    "gr\u00e2ce \ufffd vous": "gr\u00e2ce \u00e0 vous",
    "gr\u00e2ce \ufffd l'application": "gr\u00e2ce \u00e0 l'application",
    "les dana\ufffd?des": "les dana\u00efdes",
    "d\u00e9j\u00e0 \ufffdt\ufffd trait\ufffd": (
        "d\u00e9j\u00e0 \u00e9t\u00e9 trait\u00e9"
    ),
    "face \ufffd ces \nd\u00e9fis": "face \u00e0 ces \nd\u00e9fis",
    "-aspect \ufffd cao \ufffd ou \ufffd prototypage \ufffd": (
        "-Aspect \u00ab CAO \u00bb ou \u00ab prototypage \u00bb"
    ),
    "d'am\ufffdlioration": "d'am\u00e9lioration",
    "e-mail \ufffd idee@": "e-mail \u00e0 idee@",
    "analytics \n\ufffd\u00a0google\u00a0inc.": (
        "analytics \n\u00a9\u00a0google\u00a0inc."
    ),
    "acc\u00e9der \ufffd vos": "acc\u00e9der \u00e0 vos",
    "j\ufffdr\u00e9mie": "j\u00e9r\u00e9mie",
    "--\ufffd\n": "-- \n",
    "soci\u00e9t\u00e9 coop\u00e9rative \ufffd capital variable": (
        "soci\u00e9t\u00e9 coop\u00e9rative \u00e0 capital variable"
    ),
}
_CONTEXTUAL_REPLACEMENT_RULES = sorted(
    (
        (
            corrupted,
            corrected,
            corrupted[: corrupted.index("\ufffd")].casefold(),
            corrupted[corrupted.index("\ufffd") + 1 :].casefold(),
        )
        for corrupted, corrected in CONTEXTUAL_REPLACEMENTS.items()
    ),
    key=lambda rule: len(rule[0]),
    reverse=True,
)
_CONTEXTUAL_REPLACEMENTS_BY_BOUNDARY: dict[
    tuple[str | None, str | None],
    list[tuple[str, str, str, str]],
] = {}
for _rule in _CONTEXTUAL_REPLACEMENT_RULES:
    _, _, _prefix, _suffix = _rule
    _boundary = (
        _prefix[-1] if _prefix else None,
        _suffix[0] if _suffix else None,
    )
    _possible_boundaries = (
        _boundary,
        (_boundary[0], None),
        (None, _boundary[1]),
        (None, None),
    )
    for _possible_boundary in set(_possible_boundaries):
        _CONTEXTUAL_REPLACEMENTS_BY_BOUNDARY.setdefault(
            _possible_boundary, []
        ).append(_rule)
_CONTEXTUAL_REPLACEMENTS_BY_BOUNDARY = {
    boundary: list(dict.fromkeys(rules))
    for boundary, rules in _CONTEXTUAL_REPLACEMENTS_BY_BOUNDARY.items()
}
_UTF8_HTML_SIGNATURE_CLEANUP = re.compile(
    r'(?P<open>font-family:&quot;Tahoma&quot;,sans-serif">)'
    r"\ufffd{4}(?P<close></span>)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DecodedBody:
    text: str
    charset: str
    issue: str | None = None


@dataclass(frozen=True)
class Finding:
    mailbox: Path
    message_number: int
    field: str
    problem: str
    excerpt: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        _attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"head", "script", "style"}:
            self.ignored_depth += 1
        super().handle_starttag(tag, _attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"head", "script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.fragments.append(data)


def is_mbox(path: Path) -> bool:
    """Recognize mbox files by their envelope separator."""
    with path.open("rb") as stream:
        return stream.readline().startswith(b"From ")


def iter_mboxes(root: Path) -> Iterator[Path]:
    if root.is_file():
        if not is_mbox(root):
            raise ValueError(f"Not an mbox file: {root}")
        yield root
        return

    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.suffix.lower() not in IGNORED_SUFFIXES
            and is_mbox(path)
        ):
            yield path


def excerpt(text: str, focus_index: int | None = None) -> str:
    compact = " ".join(text.split())
    if len(compact) <= SNIPPET_LIMIT:
        return compact

    if focus_index is None:
        return compact[: SNIPPET_LIMIT - 3] + "..."

    compact_focus = len(" ".join(text[:focus_index].split()))
    window_size = SNIPPET_LIMIT - 6
    start = max(0, compact_focus - window_size // 2)
    end = min(len(compact), start + window_size)
    start = max(0, end - window_size)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end]}{suffix}"


def repair_mojibake(text: str) -> str | None:
    repaired = text
    for _ in range(3):
        matches = list(MOJIBAKE_PATTERN.finditer(repaired))
        if not matches:
            break
        corrected_parts: list[str] = []
        previous_end = 0
        changed = False

        for match in matches:
            corrected_parts.append(repaired[previous_end : match.start()])
            match_end = match.end()
            value = repaired[match.start() : match_end]
            candidate_values = [value]
            if value.startswith("â") and match_end < len(repaired):
                candidate_values.append(value + repaired[match_end])
            replacement = value
            repaired_match = False
            for candidate_value in candidate_values:
                for encoding in ("cp1252", "latin-1"):
                    try:
                        candidate = candidate_value.encode(encoding).decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        continue
                    if (
                        candidate != candidate_value
                        and "\ufffd" not in candidate
                        and not MOJIBAKE_PATTERN.search(candidate)
                    ):
                        changed = True
                        repaired_match = True
                        replacement = candidate
                        if candidate_value != value:
                            match_end += 1
                        break
                if repaired_match:
                    break
            corrected_parts.append(replacement)
            previous_end = match_end
        corrected_parts.append(repaired[previous_end:])

        if not changed:
            break
        repaired = "".join(corrected_parts)
    return repaired if repaired != text else None


def _canonical_charset(charset: str) -> str:
    normalized = charset.strip().strip("\"'")
    while normalized.lower().startswith("charset="):
        normalized = normalized.split("=", 1)[1].strip().strip("\"'")
    return codecs.lookup(normalized).name


def _charset_label(charset: str) -> str:
    if charset == "cp1252":
        return "Windows-1252"
    if charset == "utf-8":
        return "UTF-8"
    return charset


def _is_valid_utf8_html(part: EmailMessage, decoded: DecodedBody) -> bool:
    return (
        part.get_content_type() == "text/html"
        and decoded.issue is None
        and codecs.lookup(decoded.charset).name in {"utf-8", "utf-8-sig"}
    )


def _clean_known_utf8_html_signature(text: str) -> tuple[str, int]:
    return _UTF8_HTML_SIGNATURE_CLEANUP.subn(r"\g<open>\g<close>", text)


def _looks_like_readable_legacy_text(text: str) -> bool:
    if len(text) < 80 or not any(ord(character) > 127 for character in text):
        return False
    if MOJIBAKE_PATTERN.search(text):
        return False
    return all(
        character in "\t\n\r\f" or unicodedata.category(character) != "Cc"
        for character in text
    )


def _set_html_meta_charset(text: str, charset: str) -> str:
    return HTML_CHARSET_TEXT_PATTERN.sub(
        lambda match: f"{match.group(1)}{charset}",
        text,
        count=1,
    )


def _decode_header_value(raw_value: str) -> str | None:
    def preserve_x_user_defined_underscores(match: re.Match[str]) -> str:
        charset = match.group(1)
        payload = match.group(2).replace("_", "=5F")
        return f"=?{charset}?Q?{payload}?="

    raw_value = re.sub(r"\r?\n[ \t]+", " ", raw_value)
    if "\r" in raw_value or "\n" in raw_value:
        return None
    raw_value = re.sub(
        r"=\?(x-user-defined)\?q\?([^?]*)\?=",
        preserve_x_user_defined_underscores,
        raw_value,
        flags=re.IGNORECASE,
    )
    pieces: list[str] = []
    for fragment, declared_charset in decode_header(raw_value):
        if isinstance(fragment, str):
            pieces.append(fragment)
            continue

        candidates: list[str] = []
        if declared_charset:
            try:
                candidates.append(_canonical_charset(declared_charset))
            except LookupError:
                pass
        for fallback in ("utf-8", "cp1252", "latin-1"):
            if fallback not in candidates:
                candidates.append(fallback)

        decoded: str | None = None
        for candidate in candidates:
            try:
                decoded = fragment.decode(candidate, errors="strict")
            except UnicodeDecodeError:
                continue
            if "\ufffd" not in decoded:
                break
            decoded = None
        if decoded is None:
            return None
        pieces.append(decoded)
    return "".join(pieces)


def decode_body_part(part: EmailMessage, payload: bytes) -> DecodedBody:
    for byte_order_mark, charset in BYTE_ORDER_MARKS:
        if payload.startswith(byte_order_mark):
            try:
                text = payload.decode(charset, errors="strict")
            except UnicodeDecodeError as error:
                return DecodedBody(
                    payload.decode("utf-8", errors="replace"),
                    "utf-8",
                    f"byte-order mark indicates {_charset_label(charset)} but "
                    f"bytes {error.start}-{error.end} are invalid for that charset",
                )
            bom_charset = codecs.lookup(charset).name
            declared_charset = part.get_content_charset()
            if bom_charset == "utf-8-sig" and declared_charset:
                try:
                    if _canonical_charset(declared_charset) == "utf-8":
                        return DecodedBody(text, bom_charset)
                except LookupError:
                    pass
            return DecodedBody(
                text,
                bom_charset,
                "decoded according to the byte-order mark as "
                f"{_charset_label(charset)}",
            )

    declared_charset = part.get_content_charset()
    declared_encoding: str | None = None
    declared_error: str | None = None
    if declared_charset:
        try:
            declared_encoding = _canonical_charset(declared_charset)
        except LookupError:
            declared_error = f"unknown declared charset: {declared_charset}"

    html_charset: str | None = None
    if part.get_content_type() == "text/html":
        match = HTML_CHARSET_PATTERN.search(payload[:16384])
        if match:
            html_charset = match.group(1).decode("ascii")
            try:
                html_charset = _canonical_charset(html_charset)
            except LookupError:
                html_charset = None

    charset_mismatch = (
        part.get_content_type() == "text/html"
        and declared_encoding is not None
        and html_charset is not None
        and declared_encoding != html_charset
    )
    candidates: list[str] = []
    preferred_charsets = (
        (html_charset, declared_encoding)
        if part.get_content_type() == "text/html"
        else (declared_encoding, html_charset)
    )
    for candidate in (*preferred_charsets, "utf-8", "cp1252"):
        if candidate is not None and candidate not in candidates:
            candidates.append(candidate)

    declared_decode_error: UnicodeDecodeError | None = None
    for candidate in candidates:
        try:
            text = payload.decode(candidate, errors="strict")
        except UnicodeDecodeError as error:
            if candidate == declared_encoding:
                declared_decode_error = error
            continue
        if (
            candidate == "cp1252"
            and candidate != declared_encoding
            and any(
                ord(character) < 32 and character not in "\t\n\r\f"
                for character in text
            )
        ):
            continue

        if charset_mismatch:
            declared_label = _charset_label(declared_encoding)
            meta_label = _charset_label(html_charset)
            return DecodedBody(
                text,
                candidate,
                f"MIME charset {declared_label} conflicts with HTML meta "
                f"charset {meta_label}; decoded using {_charset_label(candidate)}",
            )
        if candidate == declared_encoding and declared_error is None:
            return DecodedBody(text, candidate)
        if (
            declared_encoding == "ascii"
            and candidate == "cp1252"
            and _looks_like_readable_legacy_text(text)
        ):
            return DecodedBody(text, candidate)
        if declared_error is not None:
            return DecodedBody(text, candidate, declared_error)
        if declared_encoding is not None:
            error = declared_decode_error
            if error is not None:
                return DecodedBody(
                    text,
                    candidate,
                    f"bytes {error.start}-{error.end} are invalid for "
                    f"{declared_charset}; decoded as {_charset_label(candidate)}",
                )
        if declared_charset is None and candidate != "utf-8":
            return DecodedBody(
                text,
                candidate,
                "no charset declared; decoded as "
                f"{_charset_label(candidate)} after invalid UTF-8",
            )
        return DecodedBody(text, candidate)

    text = payload.decode("utf-8", errors="replace")
    if declared_error is not None:
        issue = declared_error
    elif declared_encoding is not None and declared_decode_error is not None:
        issue = (
            f"bytes {declared_decode_error.start}-{declared_decode_error.end} "
            f"are invalid for {declared_charset}; no safe fallback charset found"
        )
    else:
        issue = "body cannot be decoded with UTF-8 or Windows-1252"
    return DecodedBody(text, "utf-8", issue)


def inspect_text(
    text: str,
    mailbox_path: Path,
    message_number: int,
    field: str,
) -> list[Finding]:
    findings: list[Finding] = []
    if "\ufffd" in text:
        replacement_index = text.index("\ufffd")
        findings.append(
            Finding(
                mailbox_path,
                message_number,
                field,
                "replacement character (U+FFFD); decoding may already have lost data",
                excerpt(text, replacement_index),
            )
        )
    findings.extend(inspect_mojibake(text, mailbox_path, message_number, field))
    return findings


def inspect_mojibake(
    text: str,
    mailbox_path: Path,
    message_number: int,
    field: str,
) -> list[Finding]:
    match = MOJIBAKE_PATTERN.search(text)
    if match is None:
        return []
    return [
        Finding(
            mailbox_path,
            message_number,
            field,
            "possible mojibake: text is valid Unicode but contains common mis-decoding patterns",
            excerpt(text, match.start()),
        )
    ]


def inspect_header(
    message: EmailMessage,
    name: str,
    field: str,
    mailbox_path: Path,
    message_number: int,
) -> list[Finding]:
    value = message.get(name)
    if value is None:
        return []
    raw_value = next(
        (
            raw_value
            for header_name, raw_value in message.raw_items()
            if header_name.lower() == name.lower()
        ),
        None,
    )
    decoded_value = (
        _decode_header_value(raw_value)
        if raw_value is not None
        else None
    )
    return inspect_text(
        decoded_value if decoded_value is not None else str(value),
        mailbox_path,
        message_number,
        field,
    )


def add_suspect_headers(message: EmailMessage, findings: list[Finding]) -> None:
    header_name = "X-Encoding-Suspect"
    while header_name in message:
        del message[header_name]
    for finding in findings:
        details = " ".join(
            f"{finding.field}: {finding.problem}; {finding.excerpt}".split()
        )
        details = details.encode("ascii", "backslashreplace").decode("ascii")
        details = details.replace("=?", "= ?")
        message.add_header(header_name, details)


def inspect_body_part(
    part: EmailMessage,
    mailbox_path: Path,
    message_number: int,
) -> list[Finding]:
    if part.get_content_disposition() == "attachment" or part.get_filename():
        return []
    if part.is_multipart():
        return [
            finding
            for child in part.iter_parts()
            for finding in inspect_body_part(child, mailbox_path, message_number)
        ]
    if part.get_content_type() not in {"text/plain", "text/html"}:
        return []

    payload = part.get_payload(decode=True)
    if payload is None:
        return []

    field = f"body ({part.get_content_type()})"
    decoded = decode_body_part(part, payload)
    opaque_reason = _opaque_body_reason(payload)
    if opaque_reason is not None:
        return [
            Finding(
                mailbox_path,
                message_number,
                field,
                f"opaque binary-like content ({opaque_reason}); text encoding not assessed",
                excerpt(decoded.text),
            )
        ]
    if _is_valid_utf8_html(part, decoded):
        return []

    findings = []
    if decoded.issue is not None:
        findings.append(
            Finding(
                mailbox_path,
                message_number,
                field,
                decoded.issue,
                excerpt(decoded.text),
            )
        )
    findings.extend(
        inspect_text(decoded.text, mailbox_path, message_number, field)
    )
    return findings


def inspect_message(
    message: EmailMessage,
    mailbox_path: Path,
    message_number: int,
) -> list[Finding]:
    findings = []
    findings.extend(
        inspect_header(message, "subject", "subject", mailbox_path, message_number)
    )
    findings.extend(
        inspect_header(message, "from", "sender", mailbox_path, message_number)
    )
    findings.extend(inspect_body_part(message, mailbox_path, message_number))
    return findings


def _normalized_body_text(content_type: str, text: str) -> str:
    if content_type == "text/html":
        parser = _HTMLTextExtractor()
        parser.feed(text)
        text = " ".join(parser.fragments)
    else:
        text = PLAIN_HTML_TAG_PATTERN.sub(" ", text)
        text = html.unescape(text)
    return " ".join(text.split())


def _opaque_body_reason(payload: bytes) -> str | None:
    if b"PK\x03\x04" in payload:
        return "ZIP archive signature"

    if not payload:
        return None
    for byte_order_mark, charset in BYTE_ORDER_MARKS:
        if payload.startswith(byte_order_mark):
            try:
                text = payload.decode(charset, errors="strict")
            except UnicodeDecodeError:
                break
            if text and sum(
                character.isprintable() or character in "\t\n\r\f"
                for character in text
            ) / len(text) >= 0.9:
                return None
            break

    nul_count = payload.count(b"\x00")
    if nul_count >= 16 and nul_count / len(payload) >= 0.005:
        return f"{nul_count} NUL bytes"

    control_count = sum(
        byte < 0x20 and byte not in b"\t\n\r\f"
        for byte in payload
    )
    if control_count >= 100 and control_count / len(payload) >= 0.1:
        return f"{control_count} control bytes"
    return None


def _html_visible_replacement_indices(text: str) -> set[int]:
    line_offsets = [0]
    line_offsets.extend(
        match.end() for match in re.finditer("\n", text)
    )

    class ReplacementLocator(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.indices: set[int] = set()

        def handle_data(self, data: str) -> None:
            line, column = self.getpos()
            start = line_offsets[line - 1] + column
            for match in re.finditer("\ufffd", data):
                self.indices.add(start + match.start())

    parser = ReplacementLocator()
    parser.feed(text)
    parser.close()
    return parser.indices


def _recover_text_replacements(
    text: str,
    content_type: str,
    alternatives: list[tuple[str, str]],
) -> tuple[str, int]:
    if "\ufffd" not in text or not alternatives:
        return text, 0

    normalized_text = _normalized_body_text(content_type, text)
    normalized_alternates = [
        _normalized_body_text(alternate_type, alternate_text)
        for alternate_type, alternate_text in alternatives
    ]
    visible_html_indices = (
        _html_visible_replacement_indices(text)
        if content_type == "text/html"
        else None
    )
    replacements: list[tuple[int, str]] = []
    for source_index, character in enumerate(text):
        if character != "\ufffd":
            continue
        if (
            visible_html_indices is not None
            and source_index not in visible_html_indices
        ):
            continue
        normalized_index = len(
            _normalized_body_text(content_type, text[:source_index])
        )
        candidates: set[str] = set()
        for anchor_size in (30, 15):
            left = normalized_text[
                max(0, normalized_index - anchor_size) : normalized_index
            ]
            right = normalized_text[
                normalized_index + 1 : normalized_index + anchor_size + 1
            ]
            if len(left) < 12 or len(right) < 12:
                continue
            for alternate in normalized_alternates:
                search_from = 0
                while True:
                    left_index = alternate.find(left, search_from)
                    if left_index < 0:
                        break
                    right_index = alternate.find(right, left_index + len(left))
                    if right_index >= 0 and right_index - left_index <= 100:
                        candidate = alternate[left_index + len(left) : right_index]
                        if (
                            len(candidate) == 1
                            and candidate != "\ufffd"
                            and candidate.isprintable()
                        ):
                            candidates.add(candidate)
                    search_from = left_index + 1
            if candidates:
                break

        if not candidates:
            source_token = next(
                (
                    match
                    for match in WORD_PATTERN.finditer(normalized_text)
                    if match.start() <= normalized_index < match.end()
                ),
                None,
            )
            if source_token is not None:
                token_offset = normalized_index - source_token.start()
                for alternate in normalized_alternates:
                    for alternate_token in WORD_PATTERN.finditer(alternate):
                        if len(alternate_token.group()) != len(source_token.group()):
                            continue
                        if all(
                            original == replacement
                            or original == "\ufffd"
                            for original, replacement in zip(
                                source_token.group(), alternate_token.group()
                            )
                        ):
                            candidate = alternate_token.group()[token_offset]
                            if candidate != "\ufffd" and candidate.isprintable():
                                candidates.add(candidate)
        if len(candidates) == 1:
            replacements.append((source_index, next(iter(candidates))))

    repaired = text
    for source_index, replacement in reversed(replacements):
        repaired = (
            repaired[:source_index] + replacement + repaired[source_index + 1 :]
        )
    return repaired, len(replacements)


def _repair_contextual_replacements(text: str) -> tuple[str, int]:
    if "\ufffd" not in text:
        return text, 0

    matches: list[tuple[int, int, str, str]] = []
    marker_index = text.find("\ufffd")
    while marker_index >= 0:
        before = text[marker_index - 1].casefold() if marker_index else None
        after = (
            text[marker_index + 1].casefold()
            if marker_index + 1 < len(text)
            else None
        )
        rules: list[tuple[str, str, str, str]] = []
        for boundary in (
            (before, after),
            (before, None),
            (None, after),
            (None, None),
        ):
            rules.extend(_CONTEXTUAL_REPLACEMENTS_BY_BOUNDARY.get(boundary, ()))
        for corrupted, replacement, prefix, suffix in dict.fromkeys(rules):
            start = marker_index - len(prefix)
            end = marker_index + 1 + len(suffix)
            if (
                start < 0
                or text[start:marker_index].casefold() != prefix
                or text[marker_index + 1 : end].casefold() != suffix
            ):
                continue
            original = text[start:end]
            if original.isupper():
                replacement = replacement.upper()
            elif original[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            matches.append((start, end, replacement, corrupted))
        marker_index = text.find("\ufffd", marker_index + 1)

    matches.sort(key=lambda match: (match[0], -(match[1] - match[0])))
    selected: list[tuple[int, int, str]] = []
    last_end = 0
    for start, end, replacement, _ in matches:
        if start >= last_end:
            selected.append((start, end, replacement))
            last_end = end

    repaired = text
    for start, end, replacement in reversed(selected):
        repaired = repaired[:start] + replacement + repaired[end:]
    return repaired, len(selected)


def repair_body_part(
    part: EmailMessage,
    alternatives: list[tuple[str, str]] | None = None,
) -> list[str]:
    alternatives = alternatives or []
    if part.get_content_disposition() == "attachment" or part.get_filename():
        return []
    if part.is_multipart():
        changes: list[str] = []
        for child in part.iter_parts():
            changes.extend(repair_body_part(child, alternatives))
        return changes
    if part.get_content_type() not in {"text/plain", "text/html"}:
        return []

    payload = part.get_payload(decode=True)
    if payload is None:
        return []
    if _opaque_body_reason(payload) is not None:
        return []
    decoded = decode_body_part(part, payload)
    if _is_valid_utf8_html(part, decoded):
        repaired_text, cleaned_markers = _clean_known_utf8_html_signature(
            decoded.text
        )
        recovered_replacements = 0
        if not cleaned_markers and "\ufffd" in repaired_text:
            matching_plain = [
                (content_type, text)
                for content_type, text in alternatives
                if content_type == "text/plain"
            ]
            if matching_plain:
                repaired_text, recovered_replacements = _recover_text_replacements(
                    repaired_text,
                    part.get_content_type(),
                    matching_plain,
                )
        if not cleaned_markers and not recovered_replacements:
            return []
        changes = []
        if cleaned_markers:
            changes.append(
                f"text/html: removed {cleaned_markers} unknown signature marker(s)"
            )
        if recovered_replacements:
            changes.append(
                "text/html: recovered "
                f"{recovered_replacements} replacement character(s) "
                "from text/plain alternative"
            )
        repaired_text = _set_html_meta_charset(repaired_text, "utf-8")
        content_type_params = part.get_params(header="Content-Type", unquote=True) or []
        preserved_params = [
            (name, value)
            for name, value in content_type_params[1:]
            if name.lower() != "charset"
        ]
        part.set_content(
            repaired_text,
            subtype=part.get_content_subtype(),
            charset="utf-8",
        )
        for name, value in preserved_params:
            part.set_param(name, value, header="Content-Type", replace=False)
        return changes

    repaired_text = repair_mojibake(decoded.text)
    repaired_text = repaired_text if repaired_text is not None else decoded.text
    recovered_replacements = 0
    alternative_type = (
        "text/html"
        if part.get_content_type() == "text/plain"
        else "text/plain"
    )
    matching_alternatives = [
        (content_type, text)
        for content_type, text in alternatives
        if content_type == alternative_type
    ]
    if matching_alternatives:
        repaired_text, recovered_replacements = _recover_text_replacements(
            repaired_text,
            part.get_content_type(),
            matching_alternatives,
        )
    repaired_text, contextual_fragments = _repair_contextual_replacements(
        repaired_text
    )
    if (
        decoded.issue is None
        and repaired_text == decoded.text
        and recovered_replacements == 0
        and contextual_fragments == 0
    ):
        return []

    changes = [f"{part.get_content_type()}: decoded as {_charset_label(decoded.charset)}"]
    if decoded.issue is not None and "byte-order mark" in decoded.issue:
        changes.append(decoded.issue)
    if repaired_text != decoded.text:
        if repair_mojibake(decoded.text) is not None:
            changes.append("repaired reversible mojibake")
    if recovered_replacements:
        source_type = (
            "HTML body"
            if alternative_type == "text/html"
            else "text/plain alternative"
        )
        changes.append(
            f"recovered {recovered_replacements} replacement character(s) "
            f"from {source_type}"
        )
    if contextual_fragments:
        changes.append(
            f"reconstructed {contextual_fragments} known damaged text fragment(s) "
            "from message templates"
        )
    if part.get_content_type() == "text/html":
        updated_text = _set_html_meta_charset(repaired_text, "utf-8")
        if updated_text != repaired_text:
            changes.append("aligned HTML meta charset to UTF-8")
        repaired_text = updated_text

    content_type_params = part.get_params(header="Content-Type", unquote=True) or []
    previous_charset = part.get_content_charset()
    if previous_charset is not None and previous_charset.lower() != "utf-8":
        changes.append(f"changed MIME charset from {previous_charset} to UTF-8")
    elif previous_charset is None:
        changes.append("added UTF-8 MIME charset")
    preserved_params = [
        (name, value)
        for name, value in content_type_params[1:]
        if name.lower() != "charset"
    ]
    part.set_content(
        repaired_text,
        subtype=part.get_content_subtype(),
        charset="utf-8",
    )
    for name, value in preserved_params:
        part.set_param(name, value, header="Content-Type", replace=False)
    return [f"{part.get_content_type()}: {change}" for change in changes]


def repair_message(message: EmailMessage) -> list[str]:
    changes: list[str] = []
    for header_name in ("Subject", "From"):
        current_header = message.get(header_name)
        if current_header is None:
            continue
        raw_header = next(
            (
                value
                for name, value in message.raw_items()
                if name.lower() == header_name.lower()
            ),
            None,
        )
        if raw_header is None:
            continue
        decoded_header = _decode_header_value(raw_header)
        if decoded_header is None:
            continue
        repaired_header = repair_mojibake(decoded_header) or decoded_header
        if (
            repaired_header != str(current_header)
            and "\r" not in repaired_header
            and "\n" not in repaired_header
        ):
            message.replace_header(header_name, repaired_header)
            if repair_mojibake(decoded_header) is not None:
                changes.append(f"{header_name}: repaired reversible mojibake")
            else:
                changes.append(
                    f"{header_name}: decoded RFC-2047 or unsupported charset"
                )

    alternatives = [
        (
            part.get_content_type(),
            repair_mojibake(decoded.text) or decoded.text,
        )
        for part in message.walk()
        if part.get_content_type() in {"text/plain", "text/html"}
        and part.get_content_disposition() != "attachment"
        and not part.get_filename()
        and (payload := part.get_payload(decode=True)) is not None
        and _opaque_body_reason(payload) is None
        for decoded in [decode_body_part(part, payload)]
    ]
    for part in message.walk():
        if part.is_multipart():
            continue
        changes.extend(repair_body_part(part, alternatives))
    return changes


def serialize_message(message: EmailMessage) -> bytes:
    """Serialize a message, refolding headers the stdlib cannot re-encode.

    Encoded words split mid-character (e.g. =?UTF-8?...=C3?= / =?UTF-8?...=A9?=?=)
    make the refold encode real non-ASCII chars with charset "unknown-8bit",
    which raises UnicodeEncodeError. Rebuilding the header values as plain
    decoded text sidesteps the broken encoded-word parse tree.
    """
    last_error: UnicodeEncodeError | None = None
    for _ in range(3):
        try:
            return message.as_bytes(policy=policy.default)
        except UnicodeEncodeError as error:
            last_error = error
            items = [(name, str(value)) for name, value in message.items()]
            for name in list(message.keys()):
                del message[name]
            for name, value in items:
                message[name] = value
    assert last_error is not None
    raise last_error


def add_correction_headers(message: EmailMessage, changes: list[str]) -> None:
    header_name = "X-Encoding-Correction"
    while header_name in message:
        del message[header_name]
    for change in changes:
        value = change.encode("ascii", "backslashreplace").decode("ascii")
        value = value.replace("=?", "= ?")
        message.add_header(header_name, value)


def check_tree(
    root: Path,
    suspects_mbox: Path | None = None,
    corrected_mbox: Path | None = None,
    progress: Callable[[str], None] | None = None,
    force: bool = False,
    in_place: bool = False,
    in_place_partial: bool = False,
    correction_logger: (
        Callable[[Path, int, str, str, list[str]], None] | None
    ) = None,
    only_unresolved: bool = False,
) -> tuple[int, list[Finding]]:
    if in_place_partial and not in_place:
        raise ValueError("in_place_partial requires in_place=True.")

    message_count = 0
    suspect_count = 0
    corrected_count = 0
    findings: list[Finding] = []
    unresolved_findings: list[Finding] = []
    correction_logs: list[tuple[Path, int, str, str, list[str]]] = []
    parser = BytesParser(policy=policy.default)
    output_stores: dict[str, mailbox.mbox] = {}
    created_outputs: list[Path] = []
    staged_outputs: dict[str, tuple[Path, Path]] = {}
    staged_mailboxes: dict[Path, tuple[Path, int, int, int]] = {}
    pending_mailbox_stages: set[Path] = set()
    completed = False

    output_paths = [
        path
        for path in (suspects_mbox, corrected_mbox)
        if path is not None
    ]
    resolved_outputs = [path.resolve() for path in output_paths]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError("Suspects and corrected mboxes must have different paths.")

    for output_path in output_paths:
        resolved_root = root.resolve()
        resolved_output = output_path.resolve()
        if root.is_dir() and resolved_root in resolved_output.parents:
            raise ValueError("Output mboxes must be outside the mbox/sbd tree.")
        if root.is_file() and resolved_root == resolved_output:
            raise ValueError("Output mbox must not overwrite the input mbox.")
        if not output_path.parent.is_dir():
            raise ValueError(f"Output directory does not exist: {output_path.parent}")
        if force and output_path.exists() and not output_path.is_file():
            raise ValueError(f"Output path is not a file: {output_path}")

    try:
        for key, output_path in (
            ("suspects", suspects_mbox),
            ("corrected", corrected_mbox),
        ):
            if output_path is not None:
                if force:
                    descriptor, temporary_name = tempfile.mkstemp(
                        prefix=f".{output_path.name}.",
                        suffix=".tmp",
                        dir=output_path.parent,
                    )
                    os.close(descriptor)
                    store_path = Path(temporary_name)
                    staged_outputs[key] = (store_path, output_path)
                else:
                    with output_path.open("xb"):
                        pass
                    created_outputs.append(output_path)
                    store_path = output_path
                output_stores[key] = mailbox.mbox(store_path, create=False)

        mailboxes = list(iter_mboxes(root))
        for mailbox_index, mailbox_path in enumerate(mailboxes, start=1):
            if progress is not None:
                progress(
                    f"Progress: mailbox {mailbox_index}/{len(mailboxes)}: "
                    f"{mailbox_path}; {message_count} message(s) scanned; "
                    f"{corrected_count} message(s) corrected; "
                    f"{suspect_count} suspect message(s) remain"
                )
            store = mailbox.mbox(
                mailbox_path,
                factory=lambda stream: parser.parse(stream),
            )
            staged_store: mailbox.mbox | None = None
            staged_path: Path | None = None
            original_stat = mailbox_path.stat()
            if in_place:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{mailbox_path.name}.",
                    suffix=".tmp",
                    dir=mailbox_path.parent,
                )
                os.close(descriptor)
                staged_path = Path(temporary_name)
                pending_mailbox_stages.add(staged_path)
                try:
                    shutil.copy2(mailbox_path, staged_path)
                    os.chmod(
                        staged_path,
                        stat.S_IMODE(original_stat.st_mode) | stat.S_IWUSR,
                    )
                    staged_store = mailbox.mbox(
                        staged_path,
                        factory=lambda stream: parser.parse(stream),
                        create=False,
                    )
                except BaseException:
                    staged_path.unlink(missing_ok=True)
                    pending_mailbox_stages.discard(staged_path)
                    store.close()
                    raise
            mailbox_changed = False
            try:
                for message_number, key in enumerate(store.iterkeys(), start=1):
                    message_count += 1
                    envelope = (
                        staged_store.get_message(key).get_unixfrom()
                        if staged_store is not None
                        else None
                    )
                    message = (
                        staged_store[key] if staged_store is not None else store[key]
                    )
                    message_findings = inspect_message(
                        message, mailbox_path, message_number
                    )
                    findings.extend(message_findings)
                    corrections = (
                        repair_message(message)
                        if "corrected" in output_stores or in_place
                        else []
                    )
                    if corrections:
                        add_correction_headers(message, corrections)
                        if correction_logger is not None:
                            correction_logs.append(
                                (
                                    mailbox_path,
                                    message_number,
                                    " ".join(
                                        str(message.get("Message-ID", "")).split()
                                    )
                                    or "<absent>",
                                    " ".join(str(message.get("Subject", "")).split())
                                    or "<absent>",
                                    corrections.copy(),
                                )
                            )
                    remaining_findings = (
                        inspect_message(message, mailbox_path, message_number)
                        if corrections
                        else message_findings
                    )
                    unresolved_findings.extend(remaining_findings)
                    if (
                        corrections
                        and staged_store is not None
                        and (not remaining_findings or in_place_partial)
                    ):
                        if envelope is None:
                            raise ValueError(
                                f"Missing mbox envelope line for message "
                                f"{message_number} in {mailbox_path}"
                            )
                        message.set_unixfrom(None)
                        serialized_message = serialize_message(message)
                        envelope_bytes = envelope.rstrip("\r\n").encode("ascii")
                        staged_store[key] = (
                            envelope_bytes + b"\n" + serialized_message
                        )
                        mailbox_changed = True
                    fully_repaired = bool(corrections) and not remaining_findings
                    if remaining_findings:
                        suspect_count += 1
                        if "suspects" in output_stores:
                            suspect_findings = remaining_findings
                            add_suspect_headers(message, suspect_findings)
                            output_stores["suspects"].add(serialize_message(message))
                    if fully_repaired:
                        corrected_count += 1
                        if "corrected" in output_stores:
                            output_stores["corrected"].add(serialize_message(message))
                    if progress is not None and message_count % 100 == 0:
                        progress(
                            f"Progress: {message_count} message(s) scanned "
                            f"({mailbox_index}/{len(mailboxes)} mailboxes); "
                            f"{corrected_count} message(s) corrected; "
                            f"{suspect_count} suspect message(s) remain"
                        )
            finally:
                if staged_store is not None:
                    staged_store.close()
                store.close()
            if staged_path is not None:
                if mailbox_changed:
                    staged_mailboxes[mailbox_path] = (
                        staged_path,
                        original_stat.st_size,
                        original_stat.st_mtime_ns,
                        stat.S_IMODE(original_stat.st_mode),
                    )
                else:
                    staged_path.unlink(missing_ok=True)
                pending_mailbox_stages.discard(staged_path)
            if progress is not None:
                progress(
                    f"Progress: {mailbox_index}/{len(mailboxes)} mailboxes "
                    f"completed; {message_count} message(s) scanned; "
                    f"{corrected_count} message(s) corrected; "
                    f"{suspect_count} suspect message(s) remain"
                )

        if progress is not None and not mailboxes:
            progress(
                "Progress: no mbox files found; "
                f"{corrected_count} message(s) corrected; "
                f"{suspect_count} suspect message(s) remain"
            )

        for output_store in output_stores.values():
            output_store.close()
        output_stores.clear()
        backups: dict[Path, Path] = {}
        committed_mailboxes: list[Path] = []
        output_backups: dict[Path, Path] = {}
        committed_outputs: list[Path] = []
        try:
            for mailbox_path, (
                temporary_path,
                original_size,
                original_mtime_ns,
                original_mode,
            ) in staged_mailboxes.items():
                current_stat = mailbox_path.stat()
                if (
                    current_stat.st_size != original_size
                    or current_stat.st_mtime_ns != original_mtime_ns
                ):
                    raise OSError(
                        f"Mailbox changed during scan; refusing to overwrite it: "
                        f"{mailbox_path}"
                    )
                descriptor, backup_name = tempfile.mkstemp(
                    prefix=f".{mailbox_path.name}.",
                    suffix=".bak",
                    dir=mailbox_path.parent,
                )
                os.close(descriptor)
                backup_path = Path(backup_name)
                backups[mailbox_path] = backup_path
                shutil.copy2(mailbox_path, backup_path)
                current_stat = mailbox_path.stat()
                if (
                    current_stat.st_size != original_size
                    or current_stat.st_mtime_ns != original_mtime_ns
                ):
                    raise OSError(
                        f"Mailbox changed during scan; refusing to overwrite it: "
                        f"{mailbox_path}"
                    )
                os.chmod(temporary_path, original_mode)
                os.replace(temporary_path, mailbox_path)
                committed_mailboxes.append(mailbox_path)
            for temporary_path, final_path in staged_outputs.values():
                if final_path.exists():
                    descriptor, backup_name = tempfile.mkstemp(
                        prefix=f".{final_path.name}.",
                        suffix=".bak",
                        dir=final_path.parent,
                    )
                    os.close(descriptor)
                    output_backup = Path(backup_name)
                    output_backups[final_path] = output_backup
                    shutil.copy2(final_path, output_backup)
                else:
                    created_outputs.append(final_path)
                os.replace(temporary_path, final_path)
                committed_outputs.append(final_path)
            staged_outputs.clear()
        except BaseException as error:
            rollback_errors: list[str] = []
            for final_path in reversed(committed_outputs):
                try:
                    output_backup = output_backups.get(final_path)
                    if output_backup is not None:
                        os.replace(output_backup, final_path)
                    else:
                        final_path.unlink(missing_ok=True)
                        if final_path in created_outputs:
                            created_outputs.remove(final_path)
                except OSError as rollback_error:
                    rollback_errors.append(f"{final_path}: {rollback_error}")
            for mailbox_path in reversed(committed_mailboxes):
                try:
                    os.replace(backups[mailbox_path], mailbox_path)
                except OSError as rollback_error:
                    rollback_errors.append(
                        f"{mailbox_path}: {rollback_error}"
                    )
            committed_set = set(committed_mailboxes)
            for mailbox_path, backup_path in backups.items():
                if mailbox_path not in committed_set:
                    backup_path.unlink(missing_ok=True)
            committed_output_set = set(committed_outputs)
            for final_path, output_backup in output_backups.items():
                if final_path not in committed_output_set:
                    output_backup.unlink(missing_ok=True)
            if rollback_errors:
                raise OSError(
                    f"In-place update failed ({error}); rollback also failed for "
                    + "; ".join(rollback_errors)
                ) from error
            raise
        else:
            for backup_path in backups.values():
                backup_path.unlink(missing_ok=True)
            for backup_path in output_backups.values():
                backup_path.unlink(missing_ok=True)
        staged_mailboxes.clear()
        completed = True
        if correction_logger is not None:
            for correction_log in correction_logs:
                correction_logger(*correction_log)
        return (
            message_count,
            unresolved_findings if only_unresolved else findings,
        )
    finally:
        for output_store in output_stores.values():
            output_store.close()
        if not completed:
            for temporary_path, _ in staged_outputs.values():
                temporary_path.unlink(missing_ok=True)
            for temporary_path, _, _, _ in staged_mailboxes.values():
                temporary_path.unlink(missing_ok=True)
            for temporary_path in pending_mailbox_stages:
                temporary_path.unlink(missing_ok=True)
            for output_path in created_outputs:
                output_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(
        description=(
            "Scan mbox files for invalid text encodings and likely mojibake."
        ),
        epilog=(
            "Mojibake detection is heuristic. Attachments are not inspected; "
            "only subject, sender, text/plain, and text/html are checked."
        ),
    )
    parser.add_argument(
        "root",
        type=Path,
        help="mbox/sbd directory or a single mbox file",
    )
    parser.add_argument(
        "-o",
        "--suspects-mbox",
        type=Path,
        help="create a new mbox containing each message with one or more findings",
    )
    parser.add_argument(
        "-c",
        "--corrected-mbox",
        type=Path,
        help=(
            "create a new mbox containing messages with safely repairable "
            "charset or reversible mojibake problems"
        ),
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite existing output mbox files (input files remain protected)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help=(
            "apply safe corrections directly to the scanned mbox file(s) "
            "after a successful scan"
        ),
    )
    parser.add_argument(
        "--in-place-partial",
        action="store_true",
        help=(
            "with --in-place, also save messages that still have unresolved "
            "findings after safe corrections"
        ),
    )
    args = parser.parse_args(argv)
    if not args.root.is_dir() and not args.root.is_file():
        parser.error(f"not a directory or file: {args.root}")
    if args.in_place_partial and not args.in_place:
        parser.error("--in-place-partial requires --in-place")

    def log_correction(
        mailbox_path: Path,
        message_number: int,
        message_id: str,
        subject: str,
        changes: list[str],
    ) -> None:
        print(
            f"Correction: {mailbox_path} [message {message_number}]",
            file=sys.stdout,
        )
        print(f"  Message-ID: {message_id}", file=sys.stdout)
        print(f"  Subject: {subject}", file=sys.stdout)
        for change in changes:
            print(f"  - {change}", file=sys.stdout)

    try:
        message_count, findings = check_tree(
            args.root,
            args.suspects_mbox,
            args.corrected_mbox,
            progress=lambda status: print(status, file=sys.stderr),
            force=args.force,
            in_place=args.in_place,
            in_place_partial=args.in_place_partial,
            correction_logger=log_correction,
            only_unresolved=True,
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for finding in findings:
        print(
            f"{finding.mailbox} [message {finding.message_number}] "
            f"{finding.field}: {finding.problem}\n"
            f"  {finding.excerpt}"
        )
    print(
        f"Checked {message_count} message(s); "
        f"found {len(findings)} unresolved issue(s)."
    )
    if args.suspects_mbox is not None:
        suspect_store = mailbox.mbox(args.suspects_mbox, create=False)
        try:
            suspect_count = len(suspect_store)
        finally:
            suspect_store.close()
        print(f"Wrote {suspect_count} suspect message(s) to {args.suspects_mbox}.")
    if args.corrected_mbox is not None:
        corrected_store = mailbox.mbox(args.corrected_mbox, create=False)
        try:
            corrected_count = len(corrected_store)
        finally:
            corrected_store.close()
        print(
            f"Wrote {corrected_count} automatically corrected message(s) "
            f"to {args.corrected_mbox}."
        )
    if args.in_place:
        print(f"Applied safe in-place corrections to mbox files under {args.root}.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
