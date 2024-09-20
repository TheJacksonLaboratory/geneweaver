CREATE MATERIALIZED VIEW extsrc.geneset2hom AS
SELECT g.gs_id, array_agg(h.hom_id) as hom_id_array
FROM extsrc.homology h
         INNER JOIN extsrc.geneset_value gv ON
    h.ode_gene_id = gv.ode_gene_id
         INNER JOIN production.geneset g ON gv.gs_id = g.gs_id
WHERE g.gs_status NOT LIKE 'de%'
  AND hom_id IN
      (SELECT DISTINCT hom_id
       FROM extsrc.homology)
GROUP BY g.gs_id;

CREATE INDEX geneset2hom_gs_id_index
    ON extsrc.geneset2hom (gs_id);