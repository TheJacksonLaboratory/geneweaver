/* 
Currently, this file should not be run directly.
It holds sql gists that can be helpful when debugging
and developing the databse. 
*/

/* Code that would work if foreign keys not present */
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

