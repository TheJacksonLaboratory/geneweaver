export interface OntologyTerm {
    ontology_term_id: string;
    name: string;
    description: string;
    source_ontology: string;
}

export const ontologyColorMap: { [key: string]: string } = {
    "Mesh Terms": 'green',
    "JAX Mouse Strains": 'blue',
    "Gene Ontology": "orange",
    "Mammalian Phenotype": "purple",
    "Adult Mouse Anatomy": "red",
    "EMBRACE Data and Methods": "yellow",
    "Chemical Entities of Biological Interest": "gray",
    "Human Phenotype Ontology": "bluegray",
    "Evidence and Conclusion Ontology": "pink",
    "Disease Ontology": "teal",
    "Experimental Factor Ontology": "indigo",
    "Relation Ontology": "cyan",
    "Measurement Method Ontology": "gray",
    "Vertebrate Trait Ontology": "gray",
    "Uber Anatomy Ontology": "gray",
    "Cell Ontology": "gray",
    "Mondo Disease Ontology": "gray"
}