
/* Remove files without content and foreign key links */
DELETE FROM production.file f 
WHERE f.file_contents IS NULL 
AND f.file_id=ANY(
  SELECT u.file_id 
    FROM production.file u 
  LEFT JOIN production.geneset g 
    ON g.file_id=u.file_id 
  WHERE g.file_id is NULL);