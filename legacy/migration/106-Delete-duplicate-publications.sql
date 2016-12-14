
/* Disable geneset_gs_updated Trigger */
DROP TRIGGER IF EXISTS geneset_gs_updated
ON production.geneset;

/* Update Foreign Keys */
WITH plan AS 
(
  SELECT pub_id, pub_pubmed, min(pub_id) OVER (PARTITION BY pub_pubmed) AS master_pub_id
  FROM production.publication
), 
upd_geneset AS
(
  UPDATE production.geneset g
  SET    pub_id = p.master_pub_id
  FROM   plan p
  WHERE  g.pub_id = p.pub_id
  AND    p.pub_id <> p.master_pub_id
)

/* Delete Duplicates */   
DELETE FROM production.publication c
USING  plan p
WHERE  c.pub_id = p.pub_id
AND    p.pub_id <> p.master_pub_id
RETURNING c.pub_id;

/* Re-Enable geneset_gs_updated Trigger */
CREATE TRIGGER geneset_gs_updated
BEFORE UPDATE ON production.geneset
FOR EACH ROW EXECUTE PROCEDURE production.on_geneset_updated();

/* Sanity-check: Should return 0 rows upon success */
SELECT pub_id, pub_pubmed, count(pub_pubmed) FROM production.publication GROUP BY pub_id, pub_pubmed HAVING count(pub_pubmed) > 1;
