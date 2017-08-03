CREATE OR REPLACE FUNCTION production.geneset_is_readable(test_usr_id integer, test_gs_id bigint)
    RETURNS BOOLEAN AS $$

    SELECT  true
    FROM    production.geneset
    WHERE   gs_id = $2 AND (
                -- User owns the set
                usr_id = $1 OR
                -- gs_groups indicates the set is public
                gs_groups = '0' OR
                -- The set is in a public tier
                cur_id < 5 OR
                -- The user belongs to a group that is sharing the set
                EXISTS (
                    SELECT  1
                    FROM    production.usr2grp
                    WHERE   usr_id = $1 AND
                            grp_id = ANY(('{' || geneset.gs_groups || '}') :: integer[])
                ) OR
                -- The user belongs to a group that is sharing a project that
                -- contains the set
                EXISTS (
                    SELECT      1
                    FROM        project2geneset as p2g
                    INNER JOIN  (
                        -- Get the project IDs from all the groups the user is a member of
                        SELECT      p.pj_id AS pj_id
                        FROM        production.usr2grp as u2g
                        INNER JOIN  production.project as p
                        ON          u2g.grp_id = ANY(('{' || p.pj_groups || '}') :: integer[])
                        WHERE       u2g.usr_id = $1
                    ) AS res
                    ON          p2g.pj_id IN (res.pj_id)
                    WHERE       p2g.gs_id = $2
                ) OR
                -- The user is an admin/GW curator
                EXISTS (
                    SELECT 1
                    FROM production.usr
                    WHERE usr_admin > 0 and usr_id = $1
                )
            );
    $$
    LANGUAGE SQL;
