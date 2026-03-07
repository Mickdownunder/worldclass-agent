"""Constants and keyword sets for the research planner."""
import os

PLANNER_MODEL = os.environ.get("RESEARCH_PLANNER_MODEL", "gemini-3.1-pro-preview")

_MEDICAL_KEYWORDS = frozenset({
    "medical", "medicine", "clinical", "disease", "therapy", "treatment",
    "drug", "pharmaceutical", "vaccine", "cancer", "tumor", "oncology",
    "surgery", "diagnosis", "patient", "health", "hospital", "symptom",
    "chronic", "acute", "infection", "virus", "bacteria", "antibiotic",
    "cardiac", "cardiovascular", "diabetes", "insulin", "mrna", "rna",
    "dna", "gene", "genetic", "genomic", "protein", "biomarker",
    "trial", "placebo", "efficacy", "mortality", "morbidity",
    "epidemiology", "pandemic", "pathology", "radiology", "neurology",
    "psychiatry", "immunology", "allergy", "inflammation", "transplant",
    "stem cell", "biopsy", "chemotherapy", "radiation", "prognosis",
    "fda", "ema", "who", "nih", "cdc", "pubmed", "lancet", "nejm",
    "alzheimer", "parkinson", "dementia", "stroke", "hypertension",
    "obesity", "cholesterol", "lung", "liver", "kidney", "brain",
    "mental health", "depression", "anxiety", "adhd", "autism",
    "pediatric", "geriatric", "pregnancy", "prenatal", "neonatal",
    "impfstoff", "krebs", "therapie", "krankheit", "medizin",
    "gesundheit", "arzt", "klinisch", "studie", "behandlung",
    "pdac", "crc", "nsclc", "sclc", "hcc", "rcc", "aml", "cll", "dlbcl",
    "melanoma", "melanom", "glioblastoma", "glioblastom", "sarcoma", "sarkom",
    "adenocarcinoma", "adenokarzinom", "carcinoma", "karzinom",
    "phase-1", "phase-2", "phase-3", "phase 1", "phase 2", "phase 3",
    "phase-ii", "phase-iii", "clinical trial", "klinische studie",
    "randomized", "randomisiert", "double-blind", "doppelblind",
    "recurrence-free", "disease-free", "progression-free", "overall survival",
    "rfs", "dfs", "pfs", "orr", "objective response",
    "t-zell", "t cell", "t-cell", "cd8", "cd4", "neoantigen", "neoantigen",
    "immunotherapy", "immuntherapie", "checkpoint inhibitor",
    "pd-l1", "pd-1", "atezolizumab", "pembrolizumab", "nivolumab",
    "cevumeran", "autogene", "bnt122", "ro7198457",
    "mrna vaccine", "mrna-impfstoff", "cancer vaccine", "krebsimpfstoff",
    "oncology", "onkologie", "tumor", "tumour", "metastasis", "metastase",
    "adjuvant", "neoadjuvant", "resected", "reseziert",
    "asco", "esmo", "aacr", "sabcs",
})

_NON_CLINICAL_MARKERS = {
    "manufacturing", "skalierung", "scaling", "yield", "purity",
    "cost-reduction", "cost reduction", "formulation", "formulierung",
    "supply chain", "lieferkette", "production", "produktion",
    "factory", "fabrik", "gmp", "fill-finish", "lyophilization",
    "thermostabil", "thermostable", "cold chain", "shelf life",
    "upstream", "downstream", "bioreactor", "fermentation",
}

TOPIC_STOPWORDS = {
    "neueste", "neuesten", "neuste", "neusten", "latest", "newest", "recent",
    "daten", "data", "inklusive", "including", "sowie", "also", "und", "and",
    "the", "die", "der", "das", "eine", "ein", "aus", "von", "mit", "for",
    "über", "nach", "zum", "zur", "beim",
    "welche", "welcher", "welches", "which", "what",
    "fortschritte", "fortschritt", "progress", "advances",
    "gemacht", "macht", "made", "makes",
    "gibt", "gibt's", "there", "have", "has", "been",
    "how", "wie", "warum", "why", "wann", "when",
    "kann", "können", "could", "should", "would",
    "sehr", "mehr", "most", "some", "many", "alle", "all",
    "neue", "neuer", "neues", "new",
}

PRIORITY_MAP = {"high": 1, "medium": 2, "mid": 2, "low": 3, "critical": 1, "hoch": 1, "mittel": 2, "niedrig": 3}


def get_medical_keywords():
    return _MEDICAL_KEYWORDS


def get_non_clinical_markers():
    return _NON_CLINICAL_MARKERS
