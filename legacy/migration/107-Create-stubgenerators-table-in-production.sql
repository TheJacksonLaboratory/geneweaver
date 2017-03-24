/*  stubgenerators table is being moved from old gwcuration schema to production */
CREATE TABLE IF NOT EXISTS production.stubgenerators
(
  stubgenid serial NOT NULL,
  name character varying,
  querystring character varying,
  last_update timestamp with time zone,
  usr_id integer,
  grp_id integer,
  CONSTRAINT stubgenerators_pkey PRIMARY KEY (stubgenid)
)
WITH (
  OIDS=FALSE
);
