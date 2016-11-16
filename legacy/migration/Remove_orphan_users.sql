
/* This Code is intended to delete usrs that are not referenced in any foreign key */
DELETE FROM production.usr z WHERE z.usr_id=ANY(
SELECT u.usr_id FROM production.usr u
  LEFT JOIN production.geneset g
    ON g.usr_id = u.usr_id
  LEFT JOIN production.project p
    ON p.usr_id = u.usr_id
  LEFT JOIN production.result r
    ON r.usr_id = u.usr_id
  LEFT JOIN extsrc_20150605.usr2gene x
    ON x.usr_id = u.usr_id
  LEFT JOIN production.usr2grp s
    ON s.usr_id = u.usr_id
  WHERE g.usr_id is NULL
    AND p.usr_id is NULL
    AND r.usr_id is NULL
    AND x.usr_id is NULL
    AND s.usr_id is NULL);