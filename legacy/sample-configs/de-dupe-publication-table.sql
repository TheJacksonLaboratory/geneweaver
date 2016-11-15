DELETE FROM production.publication
WHERE pub_id IN
	(SELECT production.publication.pub_id FROM production.publication
	 LEFT OUTER JOIN 
		(SELECT min(pub_id) AS delid FROM production.publication
		 GROUP BY (pub_pubmed, pub_title)) AS KeepRows
	 ON production.publication.pub_id=KeepRows.delid
WHERE KeepRows.delid IS NULL);