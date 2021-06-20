--
-- PostgreSQL database dump
--

-- Dumped from database version 13.2
-- Dumped by pg_dump version 13.1

-- Started on 2021-06-20 03:05:19 CDT

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
-- TOC entry 3297 (class 0 OID 17409)
-- Dependencies: 205
-- Data for Name: species; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.species VALUES (1, 'Mus musculus', 10090);
INSERT INTO public.species VALUES (2, 'Rattus norvegicus', 10116);
INSERT INTO public.species VALUES (3, 'Saccharomyces cerevisiae', 559292);
INSERT INTO public.species VALUES (4, 'Caenorhabditis elegans', 6239);
INSERT INTO public.species VALUES (5, 'Drosophila melanogaster', 7227);
INSERT INTO public.species VALUES (6, 'Danio rerio', 7955);
INSERT INTO public.species VALUES (7, 'Homo sapiens', 9606);
INSERT INTO public.species VALUES (8, 'Mus musculus', 10090);
INSERT INTO public.species VALUES (9, 'Rattus norvegicus', 10116);
INSERT INTO public.species VALUES (10, 'Saccharomyces cerevisiae', 559292);
INSERT INTO public.species VALUES (11, 'Caenorhabditis elegans', 6239);
INSERT INTO public.species VALUES (12, 'Drosophila melanogaster', 7227);
INSERT INTO public.species VALUES (13, 'Danio rerio', 7955);
INSERT INTO public.species VALUES (14, 'Homo sapiens', 9606);


--
-- TOC entry 3303 (class 0 OID 0)
-- Dependencies: 204
-- Name: species_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.species_id_seq', 14, true);


-- Completed on 2021-06-20 03:05:20 CDT

--
-- PostgreSQL database dump complete
--

