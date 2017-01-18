CREATE TABLE production.gs_to_pub_assignment
(
  id serial NOT NULL,
  gs_id bigint NOT NULL,
  pub_assign_id integer NOT NULL,
  CONSTRAINT gs_to_pub_assign_pkey PRIMARY KEY (id),
  CONSTRAINT gs_id_fkey FOREIGN KEY (gs_id)
      REFERENCES production.geneset (gs_id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT pub_assign_fkey FOREIGN KEY (pub_assign_id)
      REFERENCES production.pub_assignments (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION
)
WITH (
  OIDS=FALSE
);