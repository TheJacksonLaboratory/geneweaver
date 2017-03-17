
CREATE TABLE production.curation_assignments
(
  gs_id bigint NOT NULL,
  created timestamp without time zone DEFAULT now(),
  updated timestamp without time zone DEFAULT now(),
  curation_group integer NOT NULL,
  curation_state integer NOT NULL,
  curator integer DEFAULT '-1'::integer,
  reviewer integer DEFAULT '-1'::integer,
  notes character varying,
  CONSTRAINT curation_assignments_pkey PRIMARY KEY (gs_id)
)
WITH (
  OIDS=FALSE
);

