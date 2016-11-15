
DROP TRIGGER IF EXISTS geneset_gs_updated
ON production.geneset;

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
   
DELETE FROM production.publication c
USING  plan p
WHERE  c.pub_id = p.pub_id
AND    p.pub_id <> p.master_pub_id
RETURNING c.pub_id;

CREATE TRIGGER geneset_gs_updated
BEFORE UPDATE ON production.geneset
FOR EACH ROW EXECUTE PROCEDURE production.on_geneset_updated();
