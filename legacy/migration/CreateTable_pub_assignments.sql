
CREATE TABLE production.pub_assignments
(
  id serial NOT NULL,
  pub_id bigint NOT NULL,
  created timestamp without time zone DEFAULT now(),
  updated timestamp without time zone DEFAULT now(),
  curation_group integer NOT NULL,
  assignment_state integer NOT NULL,
  assignee integer DEFAULT '-1'::integer,
  assigner integer DEFAULT '-1'::integer,
  notes character varying,
  CONSTRAINT pub_assignments_pkey PRIMARY KEY (pub_id, curation_group)
)
WITH (
  OIDS=FALSE
);

