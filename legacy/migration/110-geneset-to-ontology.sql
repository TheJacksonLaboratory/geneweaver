CREATE TABLE production.geneset2ontology
(
    gs_id BIGINT NOT NULL,
    g2o_ro_ont_id INT NOT NULL,
    g2o_ont_id INT NOT NULL,
    PRIMARY KEY (gs_id, g2o_ro_ont_id, g2o_ont_id),
    CONSTRAINT g2o_geneset2ontology_geneset_gs_id_fk FOREIGN KEY (gs_id) REFERENCES production.geneset (gs_id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT g2o_geneset2ontology_ontology_ro_ont_id_fk FOREIGN KEY (g2o_ro_ont_id) REFERENCES extsrc.ontology (ont_id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT g2o_geneset2ontology_ontology_ont_id_fk FOREIGN KEY (g2o_ont_id) REFERENCES extsrc.ontology (ont_id) DEFERRABLE INITIALLY DEFERRED,
    UNIQUE (gs_id, g2o_ont_id)
);