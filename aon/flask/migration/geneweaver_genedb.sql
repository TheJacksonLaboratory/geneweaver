--
-- PostgreSQL database dump
--

-- Dumped from database version 10.13
-- Dumped by pg_dump version 13.1

-- Started on 2021-05-21 02:35:47 CDT

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 3997 (class 0 OID 16540)
-- Dependencies: 233
-- Data for Name: genedb; Type: TABLE DATA; Schema: geneweaver; Owner: odeadmin
--

INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (8, 'Unannotated', 0, 'unannotated', '2011-03-14 14:17:13.49449', 4, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (4, 'Ensembl Transcript', 0, 'ensembl transcript', '2011-03-14 14:17:13.49449', 2, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (3, 'Ensembl Protein', 0, 'ensembl protein', '2011-03-14 14:17:13.49449', 2, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (7, 'Gene Symbol', 0, 'symbol', '2011-03-14 14:17:13.49449', 4, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (10, 'MGI', 1, 'mgi', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (11, 'HGNC', 2, 'hgnc', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (12, 'RGD', 3, 'rgd', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (13, 'ZFIN', 4, 'zfin', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (14, 'FlyBase', 5, 'flybase', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (1, 'Entrez', 0, 'entrez', '2011-03-14 14:17:13.49449', 2, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (2, 'Ensembl Gene', 0, 'ensembl', '2011-03-14 14:17:13.49449', 2, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (5, 'Unigene', 0, 'unigene', '2011-03-14 14:17:13.49449', 3, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (15, 'Wormbase', 8, 'wormbase', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (16, 'SGD', 9, 'sgd', '2011-03-14 14:17:13.49449', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (17, 'miRBase', 0, 'mirbase', '2011-09-12 14:38:49.943681', 2, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (20, 'CGNC', 10, 'cgnc', '2015-06-05 18:05:13.012876', 1, NULL);
INSERT INTO geneweaver.genedb (gdb_id, gdb_name, sp_id, gdb_shortname, gdb_date, gdb_precision, gdb_linkout_url) VALUES (21, 'Variant', 0, 'variant', '2018-05-02 11:57:35.110688', 1, NULL);


--
-- TOC entry 4004 (class 0 OID 0)
-- Dependencies: 234
-- Name: genedb_gdb_id_seq; Type: SEQUENCE SET; Schema: geneweaver; Owner: odeadmin
--

SELECT pg_catalog.setval('geneweaver.genedb_gdb_id_seq', 21, true);


-- Completed on 2021-05-21 02:35:49 CDT

--
-- PostgreSQL database dump complete
--
