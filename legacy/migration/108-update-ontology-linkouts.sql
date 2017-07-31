UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://amigo.geneontology.org/amigo/term/'
WHERE   ontdb_name = 'Gene Ontology';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://informatics.jax.org/vocab/mp_ontology/'
WHERE   ontdb_name = 'Mammalian Phenotype';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://informatics.jax.org/vocab/gxd/ma_ontology/'
WHERE   ontdb_name = 'Adult Mouse Anatomy';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://ebi.ac.uk/ols/ontologies/edam/terms?iri=http://edamontology.org/'
WHERE   ontdb_name = 'EMBRACE Data and Methods';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'https://meshb.nlm.nih.gov/record/ui?ui='
WHERE   ontdb_name = 'Mesh Terms';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://amigo.geneontology.org/amigo/term/'
WHERE   ontdb_name = 'Chemical Entities of Biological Interest';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://evidenceontology.org/term/'
WHERE   ontdb_name = 'Evidence and Conclusion Ontology';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://disease-ontology.org/api/metadata/'
WHERE   ontdb_name = 'Disease Ontology';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://ebi.ac.uk/ols/ontologies/efo/terms?iri=http://www.ebi.ac.uk/efo/'
WHERE   ontdb_name = 'Experimental Factor Ontology';

UPDATE  odestatic.ontologydb 
SET     ontdb_linkout_url = 'http://compbio.charite.de/hpoweb/showterm?id='
WHERE   ontdb_name = 'Human Phenotype Ontology';
