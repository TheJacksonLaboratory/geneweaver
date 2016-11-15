/* 
Currently, this file should not be run directly.
It holds sql gists that can be helpful when debugging
and developing the databse. 
*/

/* DeDupe if no Foreign Keys present */
DELETE FROM production.publication
WHERE pub_id IN
	(SELECT production.publication.pub_id FROM production.publication
	 LEFT OUTER JOIN 
		(SELECT min(pub_id) AS delid FROM production.publication
		 GROUP BY (pub_pubmed, pub_title)) AS KeepRows
	 ON production.publication.pub_id=KeepRows.delid
WHERE KeepRows.delid IS NULL);

/* List all Primary key and Foreign Keys in the database */
SELECT conrelid::regclass AS table_from
      ,conname
      ,pg_get_constraintdef(c.oid)
FROM   pg_constraint c
JOIN   pg_namespace n ON n.oid = c.connamespace
WHERE  contype IN ('f', 'p ') 		--Optionally limit to either foreign or primary keys only
AND    n.nspname = 'production' 	--The schema on which to search for p/f keys
ORDER  BY conrelid::regclass::text, contype DESC;

/* Fix production.on_geneset_update() trigger */
CREATE OR REPLACE FUNCTION production.on_geneset_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
NEW.gs_updated := NOW();
IF NEW.gs_status = 'deleted' THEN
INSERT INTO production.genesetklist VALUES (NEW.gs_id, NOW());
END IF;
RETURN NEW;
END; $$;

DROP TRIGGER IF EXISTS geneset_gs_updated
ON production.geneset;

CREATE TRIGGER geneset_gs_updated
BEFORE UPDATE ON production.geneset
FOR EACH ROW EXECUTE PROCEDURE production.on_geneset_updated();

/* Remove Duplicates and Update FK on production.genesets table */
WITH plan AS (
   SELECT pub_id, pub_pubmed, min(pub_id) OVER (PARTITION BY pub_pubmed) AS master_pub_id
   FROM production.publication
   )
, upd_geneset AS (
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