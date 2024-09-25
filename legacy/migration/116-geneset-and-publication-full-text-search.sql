------------------------------------------------------------------------------------------------------------------------
-- GeneSets Table Search
------------------------------------------------------------------------------------------------------------------------

-- GeneSets: Alter Table
ALTER TABLE production.geneset
    ADD COLUMN gs_tsvector tsvector;

-- GeneSets: Initial tsvector creation
UPDATE geneset
SET gs_tsvector = setweight(to_tsvector('english', coalesce(gs_name, '')), 'A') ||
                  setweight(to_tsvector('english', coalesce(gs_description, '')), 'B') ||
                  setweight(to_tsvector('english', coalesce(gs_abbreviation, '')), 'C')
WHERE gs_tsvector IS NULL;

-- GeneSets: Create index on tsvector
CREATE INDEX geneset_fts_idx ON geneset USING gin (gs_tsvector);

-- GeneSets: Create update function
CREATE OR REPLACE FUNCTION geneset_tsvector_update() RETURNS trigger AS $$
BEGIN
    NEW.gs_tsvector := setweight(to_tsvector('english', coalesce(NEW.gs_name, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.gs_description, '')), 'B') ||
                        setweight(to_tsvector('english', coalesce(NEW.gs_abbreviation, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- GeneSets: Create update trigger
CREATE TRIGGER update_geneset_tsvector BEFORE INSERT OR UPDATE
    ON geneset
    FOR EACH ROW EXECUTE FUNCTION geneset_tsvector_update();


------------------------------------------------------------------------------------------------------------------------
-- Publication Table Search
------------------------------------------------------------------------------------------------------------------------
-- Publication: Alter Table
ALTER TABLE production.publication
    ADD COLUMN pub_tsvector tsvector;

-- Publication: Initial tsvector creation
UPDATE publication
SET pub_tsvector = setweight(to_tsvector('english', coalesce(pub_title, '')), 'A') ||
                   setweight(to_tsvector('english', coalesce(pub_pubmed, '')), 'A') ||
                   setweight(to_tsvector('english', coalesce(pub_authors, '')), 'B') ||
                   setweight(to_tsvector('english', coalesce(pub_abstract, '')), 'C') ||
                   setweight(to_tsvector('english', coalesce(pub_journal, '')), 'D');

-- Publication: Create index on tsvector
CREATE INDEX publication_fts_idx ON publication USING gin(pub_tsvector);

-- Publication: Create update function
CREATE OR REPLACE FUNCTION publication_tsvector_update() RETURNS trigger AS $$
BEGIN
    NEW.pub_tsvector := setweight(to_tsvector('english', coalesce(NEW.pub_title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.pub_pubmed, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(NEW.pub_authors, '')), 'B') ||
                        setweight(to_tsvector('english', coalesce(NEW.pub_abstract, '')), 'C') ||
                        setweight(to_tsvector('english', coalesce(NEW.pub_journal, '')), 'D');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Publication: Create update trigger
CREATE TRIGGER publication_tsvector_update BEFORE INSERT OR UPDATE
    ON publication
    FOR EACH ROW EXECUTE FUNCTION publication_tsvector_update();


------------------------------------------------------------------------------------------------------------------------
-- GeneSet Comprehensive Search
------------------------------------------------------------------------------------------------------------------------
CREATE MATERIALIZED VIEW production.geneset_search AS
WITH geneset_query AS (
    SELECT gs.gs_id, 'GS'||gs.gs_id AS gsid_prefixed,
           gs.gs_name AS name,
           gs.gs_description AS description,
           gs.gs_abbreviation AS label,
           gs.usr_id,
           gs.gs_count,
           gs.gs_threshold_type,
           gs.gs_gene_id_type,
           p.pub_id,
           p.pub_pubmed,
           p.pub_authors,
           p.pub_title,
           p.pub_abstract,
           p.pub_journal,
           sp.sp_name AS species,
           sp.sp_taxid AS taxid,
           COALESCE(gs.cur_id, 0) AS cur_id,
           COALESCE(gs.sp_id, 0) AS sp_id,
           COALESCE(gs.gs_attribution, 0) AS attribution,
           CASE
               WHEN gs.gs_status='provisional' THEN 1
               WHEN gs.gs_status LIKE 'deprecated%' THEN 2
               ELSE 0
               END AS gs_status,
           CASE
               WHEN gs.sp_id=1 THEN 'mouse'
               WHEN gs.sp_id=2 THEN 'human'
               WHEN gs.sp_id=3 THEN 'rat'
               WHEN gs.sp_id=4 THEN 'zebrafish'
               WHEN gs.sp_id=5 THEN 'fly'
               WHEN gs.sp_id=6 THEN 'monkey'
               WHEN gs.sp_id=8 THEN 'c. elegans'
               WHEN gs.sp_id=9 THEN 'yeast'
               END AS common_name,
           CASE
               WHEN gs.gs_threshold_type=1 THEN 'p-value'
               WHEN gs.gs_threshold_type=2 THEN 'q-value'
               WHEN gs.gs_threshold_type=3 THEN 'binary'
               WHEN gs.gs_threshold_type=4 THEN 'correlation'
               WHEN gs.gs_threshold_type=5 THEN 'effect'
               END AS threshold_name,
           CASE
               WHEN gs.gs_threshold_type=-1 THEN 'Entrez'
               WHEN gs.gs_threshold_type=-2 THEN 'Ensemble Gene'
               WHEN gs.gs_threshold_type=-3 THEN 'Ensemble Protein'
               WHEN gs.gs_threshold_type=-4 THEN 'Ensemble Transcript'
               WHEN gs.gs_threshold_type=-5 THEN 'Unigene'
               WHEN gs.gs_threshold_type=-7 THEN 'Gene Symbol'
               WHEN gs.gs_threshold_type=-8 THEN 'Unannotated'
               WHEN gs.gs_threshold_type=-10 THEN 'MGI'
               WHEN gs.gs_threshold_type=-11 THEN 'HGNC'
               WHEN gs.gs_threshold_type=-12 THEN 'RGD'
               WHEN gs.gs_threshold_type=-13 THEN 'ZFIN'
               WHEN gs.gs_threshold_type=-14 THEN 'FlyBase'
               WHEN gs.gs_threshold_type=-15 THEN 'Wormbase'
               WHEN gs.gs_threshold_type=-16 THEN 'SGD'
               WHEN gs.gs_threshold_type=-17 THEN 'miRBase'
               WHEN gs.gs_threshold_type=-20 THEN 'CGNC'
               END AS gene_id_type_name
    FROM geneset gs
             LEFT OUTER JOIN publication p USING(pub_id)
             LEFT OUTER JOIN species sp USING(sp_id)
    WHERE gs.gs_status<>'deleted'
), geneset_gene_query AS (
    SELECT gs.gs_id, STRING_AGG(ode_ref_id, ' ') AS genes
    FROM geneset gs
             JOIN geneset_value USING(gs_id)
             JOIN gene USING(ode_gene_id)
             JOIN gene_info USING(ode_gene_id)
    WHERE gs.gs_status <> 'deleted' AND gsv_in_threshold AND ode_pref
    GROUP BY gs.gs_id
), geneset_ontology_query AS (
    SELECT gso.gs_id, STRING_AGG(o.ont_ref_id || ' ' || o.ont_name || ' ' || o.ont_description, ' ') AS ontologies
    FROM ontology o
             JOIN geneset_ontology gso ON gso.ont_id = o.ont_id
             JOIN geneset gs ON gs.gs_id = gso.gs_id
    WHERE gso.gso_ref_type != 'Blacklist' AND gs.gs_status <> 'deleted'
    GROUP BY gso.gs_id
)
SELECT gq.gs_id,
       gq.usr_id,
       gq.gs_count,
       gq.pub_id,
       gq.pub_pubmed,
       gq.taxid,
       gq.cur_id,
       gq.sp_id,
       gq.gs_status,
       to_tsvector('english',
                   COALESCE(gq.gs_id::text, '') || ' ' || COALESCE(gq.gsid_prefixed, '') || ' ' ||
                   COALESCE(gq.name, '') || ' ' || COALESCE(gq.description, '') || ' ' ||
                   COALESCE(gq.threshold_name, '') || ' ' || COALESCE(gq.gene_id_type_name, '') || ' ' ||
                   COALESCE(gq.label, '') || ' ' || COALESCE(gq.pub_id::text, '') || ' ' ||
                   COALESCE(gq.pub_pubmed, '') || ' ' || COALESCE(gq.pub_authors, '') || ' ' ||
                   COALESCE(gq.pub_title, '') || ' ' || COALESCE(gq.pub_abstract, '') || ' ' ||
                   COALESCE(gq.pub_journal, '') || ' ' || COALESCE(gq.species, '') || ' ' ||
                   COALESCE(gq.taxid::text, '') || ' ' || COALESCE(gq.common_name, '') || ' ' ||
                   COALESCE(ggq.genes, '') || ' ' || COALESCE(goq.ontologies, '')
       ) AS _combined_tsvector
FROM geneset_query gq
         LEFT JOIN geneset_gene_query ggq ON gq.gs_id = ggq.gs_id
         LEFT JOIN geneset_ontology_query goq ON gq.gs_id = goq.gs_id;

CREATE INDEX geneset_search_idx ON production.geneset_search USING gin(_combined_tsvector);