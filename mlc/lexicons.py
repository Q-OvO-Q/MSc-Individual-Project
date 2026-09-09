from __future__ import annotations

import re

FLAGS = re.IGNORECASE | re.UNICODE

MU = "µμ"
LENGTH_UNIT_ABBREV = rf"(?:[{MU}]m|um|nm|mm|cm|Å|Å)"
LENGTH_UNIT_WORDS = (
    r"(?:micrometre|micrometer|micrometres|micrometers|micron|microns|"
    r"nanometre|nanometer|nanometres|nanometers|millimetre|millimeter|"
    r"millimetres|millimeters|angstrom|angstroms)"
)

CELL_LINES = (
    r"HeLa|HEK\s?293[TN]?|HEK293|U2\s?OS|U-?2\s?OS|MCF-?7|MCF-?10A|MDA-?MB-?\d+|"
    r"A549|HCT-?116|SH-?SY5Y|NIH-?3T3|3T3-?L1|CHO(?:-K1)?|COS-?7|RPE-?1|"
    r"Jurkat|K562|THP-?1|RAW\s?264\.7|Caco-?2|HepG2|Huh-?7|PC-?3|LNCaP|"
    r"SW480|DLD-?1|H1299|B16(?:F10)?|4T1|CT26|S2\s?cells|BHK|Vero|MDCK|"
    r"iPSC|hiPSC|ESC|mESC|hESC|MEF|BMDM|PBMC"
)

ORGANISMS = (
    r"mouse|mice|murine|rat|rats|human|patient|zebrafish|Danio\s+rerio|"
    r"Drosophila|fruit\s+fly|C\.\s?elegans|Caenorhabditis|Xenopus|chick(?:en)?|"
    r"rabbit|bovine|porcine|pig|sheep|macaque|monkey|primate|"
    r"Arabidopsis|tobacco|Nicotiana|maize|rice|yeast|Saccharomyces|"
    r"S\.\s?cerevisiae|S\.\s?pombe|Schizosaccharomyces|Candida|Aspergillus|"
    r"E\.\s?coli|Escherichia|Salmonella|Staphylococcus|S\.\s?aureus|"
    r"Pseudomonas|Mycobacterium|Bacillus|Listeria|Toxoplasma|Plasmodium|"
    r"Trypanosoma|Leishmania|Chlamydomonas|Dictyostelium|Tetrahymena|"
    r"bacteri(?:a|um|al)|fungal|fungus|hyphae|virus|viral|parasite|"
    r"organoid|spheroid|embryo|embryos|larva|larvae|oocyte|oocytes|"
    r"blastocyst|zygote|seedling|root\s+tip|leaf|leaves|pollen|hypocotyl"
)

TISSUES_ORGANS = (
    r"tissue|tissues|brain|cortex|cortical|hippocamp(?:us|al)|cerebell(?:um|ar)|"
    r"retina|retinal|spinal\s+cord|nerve|sciatic|liver|hepatic|kidney|renal|"
    r"glomerul(?:us|i|ar)|lung|pulmonary|alveol(?:us|i|ar)|heart|cardiac|"
    r"myocardi(?:um|al)|muscle|skeletal\s+muscle|myotube|tendon|bone|cartilage|"
    r"skin|epiderm(?:is|al)|derm(?:is|al)|intestin(?:e|al)|colon|colonic|"
    r"duodenum|ileum|jejunum|stomach|gastric|pancrea(?:s|tic)|islet|spleen|"
    r"thymus|lymph\s+node|bone\s+marrow|placenta|uterus|ovary|ovarian|testis|"
    r"testicular|prostate|bladder|thyroid|adrenal|adipose|cornea|lens|"
    r"cochlea|tumou?r|tumou?rs|xenograft|biops(?:y|ies)|carcinoma|melanoma|"
    r"glioma|glioblastoma|lesion|plaque|wound|vessel|vasculature|artery|"
    r"aorta|capillar(?:y|ies)|endotheli(?:um|al)|epitheli(?:um|al)|"
    r"blood|serum|sperm|oocyte|villi|crypt|synovium"
)

CELL_TYPES = (
    r"neuron|neurons|neuronal|astrocyte|astrocytes|microglia|oligodendrocyte|"
    r"Purkinje|photoreceptor|hair\s+cell|fibroblast|fibroblasts|myoblast|"
    r"keratinocyte|melanocyte|hepatocyte|cardiomyocyte|podocyte|osteoblast|"
    r"osteoclast|chondrocyte|adipocyte|macrophage|macrophages|monocyte|"
    r"neutrophil|eosinophil|dendritic\s+cell|T\s+cell|B\s+cell|NK\s+cell|"
    r"lymphocyte|platelet|erythrocyte|megakaryocyte|stem\s+cell|"
    r"progenitor|organoid|myotube|sperm|egg\s+cell|germ\s+cell|"
    r"cancer\s+cells?|tumou?r\s+cells?|epithelial\s+cells?|endothelial\s+cells?|"
    r"smooth\s+muscle\s+cells?|goblet\s+cell|Paneth\s+cell|enterocyte"
)

SUBCELLULAR = (
    r"nucleus|nuclei|nuclear\s+envelope|nucleol(?:us|i)|chromatin|chromosome|"
    r"chromosomes|kinetochore|centrosome|centriole|spindle|midbody|"
    r"mitochondri(?:on|a|al)|cristae|chloroplast|thylakoid|peroxisome|"
    r"lysosome|lysosomes|endosome|endosomes|autophagosome|autolysosome|"
    r"phagosome|Golgi|endoplasmic\s+reticulum|ER\s+(?:membrane|tubule|network|exit)|"
    r"plasma\s+membrane|cell\s+membrane|cytoplasm|cytosol|cytoskeleton|"
    r"actin(?:\s+(?:filaments?|cytoskeleton|cortex))?|F-actin|stress\s+fibre|"
    r"stress\s+fiber|microtubule|microtubules|tubulin|intermediate\s+filament|"
    r"lamellipodi(?:um|a)|filopodi(?:um|a)|podosome|focal\s+adhesion|"
    r"cilium|cilia|flagell(?:um|a)|axon|axons|dendrite|dendrites|"
    r"dendritic\s+spine|synapse|synapses|synaptic|growth\s+cone|"
    r"vesicle|vesicles|granule|granules|lipid\s+droplet|inclusion\s+bod(?:y|ies)|"
    r"aggregate|aggregates|biofilm|cell\s+wall|septum|nucleoid|"
    r"tight\s+junction|adherens\s+junction|desmosome|gap\s+junction|"
    r"extracellular\s+matrix|collagen\s+fibr|myelin|node\s+of\s+Ranvier"
)

SPECIFIC_OBJECT = re.compile(
    rf"\b(?:{CELL_LINES}|{ORGANISMS}|{TISSUES_ORGANS}|{CELL_TYPES}|{SUBCELLULAR})\b",
    FLAGS,
)

_HOST_SPECIES = (r"mouse|mice|rabbit|goat|donkey|rat|sheep|horse|chicken|"
                 r"guinea\s+pig|llama|alpaca|camel|human|bovine|swine|pig")
ANTIBODY_HOST_TRAP = re.compile(
    rf"\b(?:{_HOST_SPECIES})\s+(?:monoclonal\s+|polyclonal\s+|primary\s+|"
    rf"secondary\s+|IgG\d?\s+|IgM\s+)*(?=anti[- ‐])"
    rf"|\banti[- ‐](?:{_HOST_SPECIES})\b"
    rf"|\b(?:{_HOST_SPECIES})\s+(?:IgG\d?|IgM|serum|antiserum|"
    rf"(?:monoclonal|polyclonal)\s+antibod(?:y|ies))\b",
    FLAGS,
)

MODALITY_SAFE = re.compile(
    r"\b(?:"
    r"confocal(?:\s+laser\s+scanning)?|spinning[- ]disc|spinning[- ]disk|"
    r"widefield|wide[- ]field|epifluorescen(?:ce|t)|"
    r"fluorescen(?:ce|t)\s+microscop\w*|immunofluorescen(?:ce|t)|"
    r"immunocytochemistr\w*|immunohistochemistr\w*|immunostaining\s+microscop\w*|"
    r"bright[- ]?field|brightfield|dark[- ]?field|phase[- ]?contrast|"
    r"differential\s+interference\s+contrast|DIC\s+(?:image|images|micrograph|microscopy)|"
    r"polaris(?:ed|ing)\s+light|two[- ]photon|multiphoton|multi[- ]photon|"
    r"light[- ]sheet|SPIM|lattice\s+light[- ]sheet|"
    r"super[- ]resolution|STED|STORM|PALM\s+(?:imaging|microscopy)|"
    r"structured\s+illumination(?:\s+microscopy)?|SIM\s+(?:image|images|microscopy)|"
    r"TIRF|total\s+internal\s+reflection|expansion\s+microscopy|"
    r"atomic\s+force\s+microscop\w*|AFM\s+(?:image|images|topograph\w*)|"
    r"electron\s+microscop\w*|electron\s+micrograph\w*|electron\s+tomograph\w*|"
    r"transmission\s+electron|scanning\s+electron|scanning\s+transmission|"
    r"cryo[- ]?(?:EM|electron\s+microscop\w*|tomograph\w*)|"
    r"immunogold|negative\s+stain(?:ing)?\s+EM|freeze[- ]fracture|"
    r"live[- ]cell\s+imaging|time[- ]lapse\s+(?:imaging|microscopy|images)|"
    r"intravital\s+(?:imaging|microscopy)|"
    r"micrograph\w*|microscop(?:y|ic|e|es)|"
    r"histolog(?:y|ical)|histopatholog\w*|haematoxylin|hematoxylin|"
    r"H\s?&\s?E|H\s?and\s?E|"
    r"in\s+situ\s+hybridi[sz]ation|FISH\s+(?:image|images|signal)|"
    r"autoradiograph\w*|X-ray\s+crystallograph\w*|"
    r"Nomarski|toluidine\s+blue\s+section|semi[- ]thin\s+section"
    r")\b",
    FLAGS,
)

MODALITY_ACRONYM = re.compile(r"(?<![A-Za-z])(SEM|TEM|STEM|AFM|SIM|EM)(?![A-Za-z])")
STAT_SEM_GUARD = re.compile(
    r"(?:±|\+/-|\+-"
    r"|mean\s*(?:\([^)]*\))?\s*(?:±|\+/-|and|or|,)?\s*$"
    r"|(?:mean|median|average|SD|s\.?d\.?|SEM|variance|deviation)\s*"
    r"(?:±|and|or|,|/|\()?\s*$"
    r"|s\.?e\.?m|standard\s+error|error\s+bars?"
    r"|\bn\s*=\s*\d+\s*[,;(]?\s*$)", FLAGS)
EM_CONTEXT = re.compile(
    r"\b(?:electron|micrograph|microscop\w*|ultrastructur\w*|section|grid|"
    r"immunogold|tomograph\w*|topograph\w*|resolution|image|images)\b", FLAGS)

SCALE_BAR = re.compile(r"\b(?:scale|size)\s?bars?\b|\bscalebars?\b", FLAGS)

LENGTH_VALUE_ABBREV = re.compile(
    rf"(?<![\w-])\d+(?:[.,]\d+)?\s*{LENGTH_UNIT_ABBREV}(?![A-Za-z-])")
LENGTH_VALUE_WORD = re.compile(rf"\b\d+(?:[.,]\d+)?\s*{LENGTH_UNIT_WORDS}\b", FLAGS)

WAVELENGTH_GUARD = re.compile(
    r"\b(?:excit\w*|emiss\w*|laser|wavelength|λ|filter|band[- ]?pass|"
    r"bandpass|LED|diode|absorb\w*|fluoresce\w*\s+at|OD|A\d{3}|"
    r"illuminat\w*|nm\s+laser|light\s+source)\b", FLAGS)
CONCENTRATION_GUARD = re.compile(r"(?:mol|molar|concentration|treated|dose|dilut)", FLAGS)

MAGNIFICATION = re.compile(
    r"\b(?:original\s+)?magnificat\w*[^.;:\n]{0,25}?\d+"
    r"|\b(?:magnif|zoom)\w*\s*(?:of\s*)?[×x]\s*\d+"
    r"|\b\d+(?:\.\d+)?[- ]?fold\s+(?:magnif|zoom|enlarge)\w*",
    FLAGS,
)
OBJECTIVE_MAG = re.compile(
    r"\b\d{1,3}\s*[×x]\s*(?:/?\s*\d?\.?\d*\s*NA)?\s*"
    r"(?:objective|lens|oil|water|air|magnification|obj\b)"
    r"|\b(?:objective|lens)\s*[,:]?\s*\d{1,3}\s*[×x]"
    r"|\b(?:at|under|using)\s+\d{1,3}\s*[×x](?![\d\s]*10)",
    FLAGS,
)
BARE_MAG = re.compile(r"(?<![\d.])[×x]\s?\d{2,4}(?![\d.])")
BARE_MAG_GUARD = re.compile(
    r"(?:10\s*[×x]|[×x]\s*10\s*[\^⁰-⁹]|cells?|g\b|SSC|PBS|"
    r"buffer|dilut\w*|coverage|genome|\bh\b|min\b)", FLAGS)

FLUOROPHORES = (
    r"DAPI|Hoechst(?:\s?\d+)?|DRAQ5|SYTOX|SYTO\s?\d*|TO-?PRO-?\d|"
    r"[emd]?[GYCRB]FP|EGFP|eGFP|sfGFP|mGFP|mNeonGreen|mClover|Venus|mVenus|"
    r"Citrine|Cerulean|mTurquoise|mCherry|mScarlet|mKate|mRuby|mOrange|"
    r"DsRed|tdTomato|mPlum|iRFP|Halo[- ]?tag|SNAP[- ]?tag|"
    r"Alexa(?:\s?Fluor)?\s?\d{3}|Cy\s?\d|CF\d{3}|ATTO\s?\d{3}|"
    r"DyLight\s?\d{3}|Janelia\s?Fluor\s?\d{3}|JF\d{3}|BODIPY|"
    r"FITC|TRITC|TAMRA|Texas\s+Red|rhodamine|fluorescein|"
    r"phalloidin|SiR-?actin|SiR-?tubulin|"
    r"MitoTracker|LysoTracker|ERTracker|CellMask|CellTracker|CFSE|"
    r"calcein|Fluo-?4|GCaMP\d?[a-z]?|jGCaMP\w*|R-?GECO|"
    r"FM\s?1-?43|DiI|DiO|DiD|Nile\s+Red|BODIPY\s?493|"
    r"propidium\s+iodide|7-?AAD|Annexin\s?V|TUNEL|EdU|BrdU|"
    r"WGA|lectin|concanavalin\s?A|phalloidin-?\w*|"
    r"Lucifer\s+yellow|Neurobiotin|biocytin|"
    r"quantum\s+dots?|QD\d{3}"
)

HISTOSTAINS = (
    r"h(?:a)?ematoxylin|eosin|H\s?&\s?E|Masson'?s?\s+trichrome|trichrome|"
    r"periodic\s+acid[- ]Schiff|PAS\s+stain\w*|Alcian\s+blue|toluidine\s+blue|"
    r"methylene\s+blue|cresyl\s+violet|Nissl|crystal\s+violet|Giemsa|"
    r"Wright'?s?\s+stain|Congo\s+red|Sirius\s+red|Picrosirius|Oil\s+Red\s?O|"
    r"Sudan\s+(?:III|IV|black)|von\s+Kossa|Alizarin\s+red|safranin|"
    r"Gram\s+stain\w*|Ziehl[- ]Neelsen|silver\s+stain\w*|DAB|"
    r"diaminobenzidine|uranyl\s+acetate|lead\s+citrate|osmium\s+tetroxide|"
    r"X-?gal|beta-?galactosidase\s+stain\w*|Evans\s+blue|trypan\s+blue|"
    r"calcofluor|FM\s?4-?64|aniline\s+blue|Coomassie"
)

NAMED_MARKER = re.compile(rf"\b(?:{FLUOROPHORES}|{HISTOSTAINS})\b", FLAGS)

ANTIBODY = re.compile(
    r"\banti[- ‐](?:[A-Za-z0-9][\wα-ω-]{1,24})\b"
    r"|\bantibod(?:y|ies)\s+(?:against|to|directed\s+against|raised\s+against|"
    r"recogni[sz]ing|specific\s+for)\s+[\w-]+"
    r"|\bimmunolabell?ed\s+(?:for|with)\s+[\w-]+",
    FLAGS,
)

FUSION_REPORTER = re.compile(
    r"\b[\w.]{2,15}[-‐](?:GFP|EGFP|YFP|CFP|RFP|mCherry|mScarlet|tdTomato|"
    r"Venus|Halo|SNAP|mNeonGreen|mEos|Dendra)\b"
    r"|\b(?:GFP|EGFP|YFP|CFP|RFP|mCherry|mScarlet|tdTomato|Venus)[-‐][\w.]{2,15}\b",
    FLAGS,
)

STAINED_FOR = re.compile(
    r"\b(?:stained|immunostained|co-?stained|counterstained|labell?ed|"
    r"immunolabell?ed|probed|decorated|visuali[sz]ed|detected)\s+"
    r"(?:for|with|using|by)\s+((?:[A-Za-z0-9][\wα-ω./+-]*\s*){1,3})",
    FLAGS,
)
STAINED_FOR_STOPWORDS = {
    "the", "a", "an", "an antibody", "antibody", "antibodies", "confocal",
    "fluorescence", "microscopy", "immunofluorescence", "immunohistochemistry",
    "standard", "conventional", "indicated", "different", "various", "two",
    "three", "both", "specific", "appropriate", "corresponding", "respective",
    "fluorescent", "fluorescently", "secondary", "primary", "these", "this",
}

NAMED_CHANNEL = re.compile(
    rf"\b(?:{FLUOROPHORES})\s+channel\b"
    r"|\bchannel\s*(?:\(|:|,)\s*(?:red|green|blue|cyan|magenta|far[- ]?red)\b"
    r"|\b(?:red|green|blue|cyan|magenta|far[- ]?red)\s+channel\b"
    r"|\b(?:transmitted[- ]light|bright[- ]?field|DIC|reflectance)\s+channel\b",
    FLAGS,
)

COLOUR_WORD = (
    r"red|green|blue|cyan|magenta|yellow|orange|purple|violet|white|black|"
    r"grey|gray|greyscale|grayscale|far[- ]?red|pink|brown|turquoise|teal|"
    r"gold|golden"
)
COLOUR = re.compile(rf"\b(?:{COLOUR_WORD})\b", FLAGS)

COLOUR_FIXED_NAMES = re.compile(
    r"\b(?:"
    r"(?:green|red|yellow|cyan|blue|far[- ]?red|orange)\s+fluorescent\s+protein|"
    r"red\s+blood\s+cells?|white\s+blood\s+cells?|"
    r"white\s+matter|gr[ae]y\s+matter|brown\s+adipose|brown\s+fat|"
    r"trypan\s+blue|evans\s+blue|methylene\s+blue|toluidine\s+blue|"
    r"alcian\s+blue|coomassie(?:\s+brilliant)?\s+blue|bromophenol\s+blue|"
    r"aniline\s+blue|calcofluor\s+white|nile\s+red|oil\s+red\s?o|congo\s+red|"
    r"sirius\s+red|neutral\s+red|texas\s+red|malachite\s+green|fast\s+green|"
    r"light\s+green|methyl\s+green|janus\s+green|indocyanine\s+green|"
    r"crystal\s+violet|cresyl\s+violet|gentian\s+violet|ethyl\s+violet|"
    r"blue\s+native|green\s+tea|black\s+box|white\s+noise|"
    r"(?:blue|green|red|white|UV)\s+light|(?:blue|green|red)\s+laser|"
    r"gr[ae]y\s?scale|black\s+and\s+white|white\s+space|"
    r"green\s+algae|blue[- ]?green\s+algae|red\s+algae|"
    r"white\s+arrow\w*|black\s+arrow\w*|yellow\s+arrow\w*|red\s+arrow\w*|"
    r"white\s+asterisk\w*|black\s+asterisk\w*|"
    r"white\s+(?:dashed\s+)?lines?|yellow\s+(?:dashed\s+)?lines?|"
    r"white\s+(?:box|boxes|square|rectangle|circle|outline)\w*|"
    r"yellow\s+(?:box|boxes|square|rectangle|circle|outline)\w*|"
    r"white\s+bars?|black\s+bars?|gr[ae]y\s+bars?|"
    r"black\s+dots?|white\s+dots?|open\s+and\s+closed"
    r")\b",
    FLAGS,
)

MAPPING_TARGET = re.compile(
    rf"\b(?:{FLUOROPHORES}|{HISTOSTAINS}|{SUBCELLULAR}|{CELL_TYPES}|"
    r"signal|signals|staining|stain|label|labelling|labeling|"
    r"immunoreactivity|fluorescence|expression|reporter|marker|markers|"
    r"protein|proteins|antibody|puncta|nuclei|nucleus|membrane|cytoplasm|"
    r"merge|merged|overlay|composite|channel|channels|"
    r"anti[- ]?[A-Za-z0-9][\w-]{1,20}"
    r")\b",
    FLAGS,
)

MAP_LINK_VERB = (
    r"indicates?|indicated|shows?|shown|marks?|marked|denotes?|denoted|"
    r"labels?|labelled|labeled|represents?|represented|corresponds?\s+to|"
    r"is|are|was|were|depicts?|highlights?|identifies|reveals?|"
    r"pseudo-?colou?red|colou?r-?coded|colou?red|rendered|displayed|"
    r"painted(?:\s+in)?|due\s+to|stands?\s+for"
)

_OPEN_TARGET = r"[A-Za-z][\w.:/+-]{1,30}"
GENERIC_COLOUR_TARGET = {
    "signal", "signals", "staining", "stain", "stains", "fluorescence",
    "label", "labels", "labelling", "labeling", "immunoreactivity",
    "expression", "image", "images", "panel", "panels", "channel", "channels",
}

_MAP_STOP_TARGET = {
    "the", "a", "an", "in", "of", "and", "or", "with", "for", "from", "to",
    "as", "is", "are", "was", "were", "at", "on", "by", "shown", "scale",
    "bar", "bars", "panel", "panels", "arrow", "arrows", "arrowhead",
    "arrowheads", "line", "lines", "box", "boxes", "circle", "circles",
    "asterisk", "asterisks", "star", "stars", "dot", "dots", "square",
    "squares", "outline", "outlines", "inset", "insets", "symbol", "symbols",
    "curve", "curves", "trace", "traces", "text", "letter", "letters",
}
OPEN_TARGET_THEN_COLOUR = re.compile(
    rf"(?P<t>{_OPEN_TARGET})\s*\(\s*(?:pseudo-?colou?red\s+)?(?P<c>{COLOUR_WORD})\s*\)",
    FLAGS)
OPEN_TARGET_IN_COLOUR = re.compile(
    rf"(?P<t>{_OPEN_TARGET})\s*(?:,|;|:|=)?\s*"
    rf"(?:{MAP_LINK_VERB})?\s*(?:shown\s+)?(?:in|as)\s+(?P<c>{COLOUR_WORD})\b",
    FLAGS)
OPEN_TARGET_COPULA_COLOUR = re.compile(
    rf"(?P<t>{_OPEN_TARGET})\s*(?:,|;|:|=)?\s*"
    rf"(?:is|are|was|were|appears?|appeared|looks?)\s+"
    rf"(?:shown\s+|displayed\s+|rendered\s+|colou?red\s+)?"
    rf"(?P<c>{COLOUR_WORD})\b",
    FLAGS)

PANEL_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])\((?P<p1>[A-Za-z](?:['′]?)?)\)"
    r"|(?:^|(?<=[.;:!?]\s)|(?<=—\s))(?P<p2>[A-H])[.)]\s"
    r"|\bpanels?\s+(?P<p3>[A-Z])\b",
)
PANEL_RANGE = re.compile(r"\(?\b[A-Z]\s?[-–—]\s?[A-Z]\b\)?")

PANEL_LOWER = re.compile(
    r"(?:^|(?<=[.;:!?]\s)|(?<=\)\s))"
    r"(?P<pl>[a-z](?:\s?[-–—]\s?[a-z])?(?:\s?,\s?[a-z])*)\s?,\s+"
    r"(?=[A-Za-z0-9])")
_PANEL_NOUN = (r"panel|panels|image|images|row|rows|column|columns|micrograph|"
               r"micrographs|inset|insets|field|fields|half|side|part|lane|"
               r"lanes|graph|graphs|plot|plots|trace|traces|track|tracks")

POSITION_WORD = re.compile(
    r"\b(?:left|right|top|bottom|upper|lower|middle|centre|center|"
    r"leftmost|rightmost|uppermost|topmost|bottommost)\b"
    r"(?:\s+(?:hand|most))?"
    rf"(?:\s+(?:{_PANEL_NOUN}))?"
    rf"|\b(?:first|second|third|fourth|fifth|last|final)\s+(?:{_PANEL_NOUN})\b"
    rf"|\b(?:{_PANEL_NOUN})\s+(?:1|2|3|4|5|one|two|three|four|five)\b",
    FLAGS,
)
CROSSREF_GUARD = re.compile(
    r"\b(?:see|in|from|of|shown\s+in|as\s+in|quantif\w*\s+(?:of|in)|"
    r"data\s+(?:in|from)|Fig(?:ure)?s?\.?\s?\d*|panels?\s+in)\s*$", FLAGS)

CONDITION_WORD = re.compile(
    r"\b(?:control|controls|untreated|treated|treatment|vehicle|DMSO|mock|"
    r"wild[- ]?type|WT|mutant|mutants|knock[- ]?out|knockout|KO|knock[- ]?down|"
    r"knockdown|siRNA|shRNA|sgRNA|CRISPR|overexpress\w*|transfect\w*|"
    r"infected|uninfected|stimulated|unstimulated|induced|uninduced|"
    r"before|after|baseline|recovery|washout|dose|concentration|"
    r"\d+\s*(?:h|hr|hrs|hours|min|minutes|days?|weeks?)\b|"
    r"merge|merged|overlay|composite|zoom|inset|magnified|enlarged|"
    r"quantification\s+of|scheme|schematic|"
    r"day\s?\d+|P\d+|E\d+\.?\d*|stage\s+\w+|"
    r"patients?|healthy|disease[d]?|tumou?r|normal|sham|injured|"
    r"low|high|young|old|male|female|"
    r"\+\s?/?\s?[-+]|−/−|-/-|\+/\+"
    r")\b",
    FLAGS,
)

ANNOTATION_NOUN = (
    r"arrows?|arrowheads?|asterisks?|stars?|daggers?|carets?|"
    r"boxes?|boxed\s+(?:regions?|areas?)|squares?|rectangles?|circles?|"
    r"ellipses?|outlines?|contours?|brackets?|braces?|"
    r"dashed\s+(?:lines?|boxes?|circles?|outlines?)|dotted\s+lines?|"
    r"solid\s+lines?|white\s+lines?|yellow\s+lines?|"
    r"insets?|magnified\s+(?:regions?|views?|areas?|insets?)|"
    r"enlarged\s+(?:regions?|views?|areas?|insets?)|"
    r"crosshairs?|markers?|symbols?|labels?|annotations?|overlays?|"
    r"colou?r\s+bars?|lookup\s+tables?|LUTs?|"
    r"hashtags?|number\s+signs?|pound\s+signs?|plus\s+signs?|"
    r"triangles?|diamonds?|chevrons?|tick\s+marks?"
)
ANNOTATION_TOKEN = re.compile(rf"\b(?:{ANNOTATION_NOUN})\b", FLAGS)

EXPLAIN_VERB = (
    r"indicates?|indicated|indicating|shows?|shown|showing|marks?|marked|"
    r"marking|denotes?|denoted|denoting|highlights?|highlighted|"
    r"points?\s+to|pointing\s+to|represents?|represented|identif(?:y|ies|ied)|"
    r"label(?:s|led|ed|ling)?|delineates?|outlines?|outlined|"
    r"demarcates?|corresponds?\s+to|refers?\s+to|"
    r"is|are|was|were|=|:"
)

ANNOTATION_TRAP = re.compile(
    r"\b(?:error\s+bars?|scale\s?bars?|size\s?bars?|bar\s+(?:graph|chart|plot)s?|"
    r"box\s?plots?|boxes\s+(?:and|show)\s+whisker|whisker\s+plots?|"
    r"box\s+and\s+whisker|"
    r"asterisks?\s*(?:indicate[sd]?|denote[sd]?|represent|show)?\s*"
    r"(?:statistical\s+)?significan\w*|"
    r"\*+\s*(?:p|P)\s*[<>=≤]|"
    r"(?:p|P)\s*[<>=≤]\s*0?\.\d+|"
    r"n\.?s\.?\s*[,=]|"
    r"legend\s+(?:box|key)|colou?r\s+key"
    r")", FLAGS)

MAGNIFY_INSTRUCTION = re.compile(
    r"\b(?:boxed|outlined|dashed|framed|white|yellow|highlighted)?\s*"
    r"(?:regions?|areas?|insets?|views?|fields?|squares?|boxes?)\s+"
    r"(?:are|is|was|were|shown|magnified|enlarged|zoomed)"
    r"[^.;]{0,60}?(?:magnif\w*|enlarg\w*|zoom\w*|higher\s+magnification|"
    r"shown\s+(?:in|at|on)|below|right|bottom|adjacent)"
    r"|\b(?:higher|high)[- ]magnification\s+(?:views?|images?|insets?)\s+of"
    r"|\b(?:insets?|boxed\s+regions?)\s*(?:,|:)?\s*(?:higher|magnified|enlarged|"
    r"\d+[×x])",
    FLAGS,
)

MICROSCOPY_STRONG = re.compile(
    r"\b(?:confocal|micrograph\w*|microscop\w*|immunofluorescen\w*|"
    r"immunohistochemi\w*|immunocytochemi\w*|epifluorescen\w*|"
    r"bright[- ]?field|brightfield|phase[- ]?contrast|widefield|wide[- ]field|"
    r"light[- ]sheet|two[- ]photon|multiphoton|super[- ]resolution|"
    r"STED|STORM|TIRF|electron\s+microscop\w*|cryo[- ]?EM|ultrastructur\w*|"
    r"histolog\w*|histopatholog\w*|H\s?&\s?E|haematoxylin|hematoxylin|"
    r"scale\s?bars?|DAPI|Hoechst|phalloidin|MitoTracker|LysoTracker|"
    r"immunogold|time[- ]lapse\s+(?:imaging|microscopy)|live[- ]cell\s+imaging|"
    r"in\s+situ\s+hybridi[sz]ation)\b",
    FLAGS,
)
MICROSCOPY_WEAK = re.compile(
    r"\b(?:GFP|mCherry|tdTomato|Alexa(?:\s?Fluor)?\s?\d{3}|fluorescen\w*|"
    r"stained|staining|immunostain\w*|labell?ed|imaged|imaging|images?|"
    r"section\w*|nuclei|nucleus|cytoplasm|membrane|cells?)\b",
    FLAGS,
)
NON_IMAGE_FIGURE = re.compile(
    r"\b(?:western\s+blot|immunoblot|blotting|SDS[- ]PAGE|gel\s+electrophoresis|"
    r"agarose\s+gel|coomassie|qPCR|RT[- ]?(?:q)?PCR|ELISA|"
    r"flow\s+cytometr\w*|FACS|mass\s+spectrometr\w*|chromatograph\w*|"
    r"Kaplan[- ]Meier|survival\s+curve|volcano\s+plot|heat\s?map|"
    r"principal\s+component|UMAP|t-?SNE|phylogenetic\s+tree|"
    r"MRI|magnetic\s+resonance|computed\s+tomograph\w*|\bCT\s+scan|"
    r"ultrasound|radiograph\w*|PET\s+scan|"
    r"crystal\s+structure|ribbon\s+diagram|molecular\s+dynamics|"
    r"schematic|diagram|workflow|flow\s?chart|model\s+of|cartoon)\b",
    FLAGS,
)

MICROGRAPH_STRONG = re.compile(
    r"\b(?:confocal|micrograph\w*|epifluorescen\w*|immunofluorescen\w*|"
    r"immunohistochemi\w*|immunocytochemi\w*|histolog\w*|histopatholog\w*|"
    r"bright[- ]?field|brightfield|dark[- ]?field|phase[- ]?contrast|"
    r"widefield|wide[- ]field|light[- ]sheet|two[- ]photon|multiphoton|"
    r"super[- ]resolution|STED|STORM|TIRF|structured\s+illumination|"
    r"electron\s+microscop\w*|scanning\s+electron|transmission\s+electron|"
    r"atomic\s+force\s+microscop\w*|"
    r"time[- ]?lapse|live[- ]cell\s+imaging|intravital|"
    r"in\s+situ\s+hybridi[sz]ation|smFISH|single[- ]molecule\s+imag\w*|"
    r"photomicrograph\w*|microscop(?:y|e|es|ic\s+image)|"
    r"H\s?&\s?E|h(?:a)?ematoxylin|toluidine\s+blue\s+section)\b", FLAGS)

SPECIMEN_EVIDENCE = re.compile(
    rf"\b(?:{CELL_LINES}|{ORGANISMS}|{TISSUES_ORGANS}|"
    rf"{CELL_TYPES}|{SUBCELLULAR})\b", FLAGS)

SCALE_EVIDENCE = re.compile(r"\b(?:scale\s?bars?|scalebars?|magnificat\w*)\b", FLAGS)

STRUCTURE = re.compile(
    r"\b(?:cryo-?EM\s+(?:map|density|structure|reconstruction)|"
    r"crystal\s+structure|atomic\s+model|density\s+map|"
    r"ribbon\s+(?:representation|diagram)|surface\s+representation|"
    r"electrostatic\s+surface|stereo\s?view|PDB(?:\s+code)?|"
    r"b-?factor|contoured\s+at|superimposed\s+on\s+the|"
    r"TM\d|alpha-?helix|beta-?(?:sheet|strand)|angstrom|Å|"
    r"molecular\s+dynamics|docking|homology\s+model|"
    r"symmetry\s+axis|capsomer|protomer|"
    r"residues?\s+(?:[A-Z][a-z]{2}\d+))", FLAGS)

GEL = re.compile(
    r"\b(?:western\s+blot\w*|immunoblot\w*|SDS[- ]?PAGE|native\s+PAGE|"
    r"agarose\s+gel|gel\s+electrophoresis|EMSA|2D\s+gel|"
    r"coomassie|loading\s+control|lanes?\s+were|input\s+\(|"
    r"immunoprecipitat\w*|pull[- ]down|autoradiograph\w*)\b", FLAGS)

PLOT = re.compile(
    r"\b(?:bar\s+(?:graph|chart|plot)s?|box\s?plots?|violin\s+plots?|"
    r"scatter\s?plots?|line\s+graph\w*|histogram\w*|"
    r"survival\s+curve|Kaplan[- ]Meier|volcano\s+plot|heat\s?maps?|"
    r"dose[- ]response|growth\s+curve|time\s+course\s+of|"
    r"raster\s+plot\w*|peristimulus|PSTH|sample\s+traces|"
    r"representative\s+traces|current\s+traces|"
    r"UMAP|t-?SNE|principal\s+component|PCA\s+plot|"
    r"venn\s+diagram|correlation\s+plot|"
    r"mean\s*(?:±|\+/-)\s*(?:SEM|SD)|error\s+bars?|"
    r"quantificat\w*\s+of|percentage\s+of|"
    r"flow\s+cytometr\w*|FACS|OD\s?\d{3}|"
    r"axis|y-?axis|x-?axis)\b", FLAGS)

SCHEMATIC = re.compile(
    r"\b(?:schematic\w*|diagram\w*|cartoon\w*|flow\s?chart\w*|workflow|"
    r"illustration\s+of|model\s+of\s+the|graphical\s+(?:model|abstract)|"
    r"experimental\s+(?:design|timeline|paradigm|strategy)|"
    r"phylogenetic\s+tree|network\s+diagram|circuit\s+diagram|"
    r"depicting\s+the\s+strategy|outline\s+of\s+the)\b", FLAGS)
