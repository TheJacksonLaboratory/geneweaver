ALTER TABLE production.pub_assignments DROP CONSTRAINT pub_assignments_pkey;
ALTER TABLE production.pub_assignments ADD CONSTRAINT pub_assignments_pkey PRIMARY KEY (id);