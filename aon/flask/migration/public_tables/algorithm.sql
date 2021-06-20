--
-- PostgreSQL database dump
--

-- Dumped from database version 13.2
-- Dumped by pg_dump version 13.1

-- Started on 2021-06-20 02:57:25 CDT

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
-- TOC entry 3299 (class 0 OID 17396)
-- Dependencies: 203
-- Data for Name: algorithm; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.algorithm VALUES (1, 'Ensembl Compara');
INSERT INTO public.algorithm VALUES (2, 'PANTHER');
INSERT INTO public.algorithm VALUES (3, 'TreeFam');
INSERT INTO public.algorithm VALUES (4, 'Roundup');
INSERT INTO public.algorithm VALUES (5, 'OrthoFinder');
INSERT INTO public.algorithm VALUES (6, 'InParanoid');
INSERT INTO public.algorithm VALUES (7, 'OMA');
INSERT INTO public.algorithm VALUES (8, 'Hieranoid');
INSERT INTO public.algorithm VALUES (9, 'PhylomeDB');
INSERT INTO public.algorithm VALUES (10, 'OrthoInspector');
INSERT INTO public.algorithm VALUES (11, 'HGNC');
INSERT INTO public.algorithm VALUES (12, 'ZFIN');


--
-- TOC entry 3305 (class 0 OID 0)
-- Dependencies: 202
-- Name: algorithm_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.algorithm_id_seq', 13, true);


-- Completed on 2021-06-20 02:57:26 CDT

--
-- PostgreSQL database dump complete
--

