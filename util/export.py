import srsly
import shutil
from pathlib import Path
from typing import List
from spacy.tokens import Doc, Span
from spacy.matcher import PhraseMatcher


def download(lang_name:str):
    #confirm json lookups are valid 
    new_lang = Path.cwd() / "new_lang"
    lookups_path = new_lang / "lookups"
    for lookup in lookups_path.iterdir():
        key = lookup.stem[lookup.stem.find('_') + 1:]
        if 'lemma' in key:
            lemma_data = srsly.read_json(lookup)
            
        if 'entity' in key:
            entity_data = srsly.read_json(lookup)
            
        if 'pos' in key:
            pos_data = srsly.read_json(lookup)
            
    
    #if valid, continue
    texts = get_texts()
    filenames = get_filenames()
    nlp = get_nlp(lang_name)
    if texts and nlp: 
        docs = [doc for doc in list(nlp.pipe(texts))]
        
        # let each Doc remember the file it came from
        for doc, filename in zip(docs,filenames):
            doc.user_data['filename'] =  filename

        docs = update_tokens_with_lookups(nlp, docs)
        conll = [doc_to_conll(doc) for doc in docs]

        temp_path = Path('/tmp/conll_export')
        temp_path.mkdir(parents=True, exist_ok=True)
        for filename, conll in zip(filenames,conll):
            conll_filename = filename.split('.')[0] +'.conll'
            (temp_path / conll_filename).write_text(conll)

        #shutil.make_archive("zipped_sample_directory", "zip", "sample_directory")
        shutil.make_archive(str(temp_path), 'zip', str(temp_path))
        zip_file = str(temp_path).split('/')[-1]+'.zip'
        #save each doc to a file, return single zip file with all CONFIRM, can import directory into INCEpTION

        return f'saved data to file /tmp/conll_export.zip'

def get_filenames() -> List[str]:
    new_lang = Path.cwd() / "new_lang"
    texts_path = new_lang / "texts"
    if not texts_path.exists():
        return None
    filenames = [text.name for text in texts_path.iterdir()]
    return filenames

def get_texts() -> List[str]:
    new_lang = Path.cwd() / "new_lang"
    texts_path = new_lang / "texts"
    if not texts_path.exists():
        return None
    texts = [text.read_text() for text in texts_path.iterdir()]
    return texts

def get_nlp(lang_name:str):
    # Load language object as nlp
    new_lang = Path.cwd() / "new_lang"
    try:
        mod = __import__(f"new_lang", fromlist=[lang_name.capitalize()])
    except SyntaxError:  # Unable to load __init__ due to syntax error
        # redirect /edit?file_name=examples.py
        message = "[*] SyntaxError, please correct this file to proceed."
        print(message)
    cls = getattr(mod, lang_name.capitalize())
    nlp = cls()
    return nlp


def update_tokens_with_lookups(nlp, docs:List[Doc]) -> List[Doc]:

    #Read the lookups directory, make dict of table names and path to json files
    new_lang = Path.cwd() / "new_lang"
    lookups_path = new_lang / "lookups"
    for lookup in lookups_path.iterdir():
        key = lookup.stem[lookup.stem.find('_') + 1:]
        if 'lemma' in key:
            lemma_data = srsly.read_json(lookup)
            assert isinstance(lemma_data, dict)

        if 'entity' in key:
            entity_data = srsly.read_json(lookup)
            assert isinstance(entity_data, dict)
        if 'pos' in key:
            pos_data = srsly.read_json(lookup)
            assert isinstance(pos_data, dict)

    matcher = PhraseMatcher(nlp.vocab)
    try:
        for ent in entity_data.keys():
                matcher.add(ent, [nlp(ent)])
    except AttributeError as e:
        print(e)

    for doc in docs:
        for t in doc:
            
            lemma = lemma_data.get(t.text, None)
            if lemma:
                t.lemma_ = lemma
            
            pos = pos_data.get(t.text, None)
            if pos:
                try:
                    t.pos_ = pos
                except Exception as e: 
                    print(e)
            
        matches = matcher(doc)
        for match_id, start, end in matches:
            string_id = nlp.vocab.strings[match_id]
            #ent_label = entity_data.get(string_id, None)
            span = Span(doc, start, end, label=string_id)
            if doc.spans.get('ents',None):
                doc.spans['ents'].append(span)
            else:
                doc.spans["ents"] = [span]


    return docs

def load_ents(doc):
    """Take a Doc object with ent spans.  Use the lookups to label 
    each token in the Doc using the token's index. Returns a dictionary with the 
    token index as key and the entity label as value. If
    #TODO This does not handle overlapping entities! When a token is part of two overlapping ent 
    spans, it will only record the last ent-span.  There's no way to account for multiple-ents in the 
    CoreNLP CoNLL format, so that's my excuse. Please prove me wrong.  

    Args:
        doc (Doc): a spaCy doc object with entries in doc.spans['ents']

    Returns:
        dict: ent lookup by token index
    """
    new_lang = Path.cwd() / "new_lang"
    lookups_path = new_lang / "lookups"
    for lookup in lookups_path.iterdir():
        key = lookup.stem[lookup.stem.find('_') + 1:]
        if 'entity' in key:
            entity_data = srsly.read_json(lookup)
            assert isinstance(entity_data, dict)
    tokens_with_ents = {}
    if doc.spans.get('ents', None):
        for span in doc.spans['ents']:
            ent = entity_data.get(span.text,None)
            for t in span:
                tokens_with_ents[t.i] = ent
    return tokens_with_ents

def doc_to_conll(doc) -> str:
    """
    Converts a spaCy Doc object to string formatted using CoreNLP CoNLL format for pos, lemma and entity
    https://dkpro.github.io/dkpro-core/releases/2.2.0/docs/format-reference.html#format-ConllCoreNlp
    
    The CoreNLP CoNLL format is used by the Stanford CoreNLP package. 
    Columns are tab-separated. Sentences are separated by a blank new line.

    example:
    1	Selectum	Selectum	NNP	O	_	_
    2	,	,	,	O	_	_
    3	Société	Société	NNP	O	_	_
    4	d'Investissement	d'Investissement	NNP	O	_	_
    5	à	à	NNP	O	_	_
    6	Capital	Capital	NNP	O	_	_
    7	Variable	Variable	NNP	O	_	_
    8	.	.	.	O	_	_
    
    Args:
        doc ([type]): [description]
    """
    data = []
    
    tokens_with_ents = load_ents(doc)

    for tok in doc:
        

        if tok.is_space:
            form = "_"
            lemma = "_"
        else:
            form = tok.orth_
            lemma = tok.lemma_
        tok_id = tok.i +1
        
        misc = "SpaceAfter=No" if not tok.whitespace_ else "_"
        row = {}
        
        row["ID"] = str(tok_id) # Token counter, starting at 1 for each new sentence.
        row["FORM"] = "_" if form == '' else form #Word form or punctuation symbol.
        row["LEMMA"] = '_' if lemma == '' else lemma #Lemma of the word form.        
        row["POSTAG"] = "_" if tok.pos_ == '' else tok.pos_ #Fine-grained part-of-speech tag
        #Named Entity tag, or underscore if not available. 
        # If a named entity covers multiple tokens, all of the tokens simply carry 
        # the same label without (no sequence encoding).
        # INCEpTION interprets this data as ent spans, yay! 
        if tok.i in tokens_with_ents.keys():
            row["NER"] = tokens_with_ents[tok.i]
        else:
            row["NER"] = "_" 
        row["HEAD"] = "_"
        row["DEPREL"] = "_"
        
        data.append(row)
    output_file = f""""""
    for row in data:
        for column in row.keys():
            if column == "DEPREL":
                output_file += row[column] + '\n'
            else:
                output_file += row[column] + '\t'
    return output_file
