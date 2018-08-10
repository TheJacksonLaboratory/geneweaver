CREATE OR REPLACE FUNCTION production.create_geneset_for_queue(integer, integer, integer, integer, character varying, character varying, character varying, integer, character varying, integer, character varying, character varying, character varying, integer, text)
 RETURNS bigint
 LANGUAGE plpgsql
AS $function$
DECLARE
--- create_geneset(
   my_usr_id ALIAS FOR $1;
   my_cur_id ALIAS FOR $2;
   my_sp_id ALIAS FOR $3;
   my_gs_threshold_type ALIAS FOR $4;
   my_gs_threshold ALIAS FOR $5;
   my_gs_groups ALIAS FOR $6;
   my_gs_status ALIAS FOR $7;
   my_gs_count ALIAS FOR $8;
   my_gs_uri ALIAS FOR $9;
   my_gs_gene_id_type ALIAS FOR $10;
   my_gs_name ALIAS FOR $11;
   my_gs_abbreviation ALIAS FOR $12;
   my_gs_description ALIAS FOR $13;
   my_gs_attribution ALIAS FOR $14;
   my_file_contents ALIAS FOR $15;
-- ) returns:
   my_gs_id BIGINT;

-- creates in the process:
   my_file_id BIGINT;
BEGIN

 INSERT INTO production.file (file_contents,file_created)
   VALUES (my_file_contents, NOW())
   RETURNING file_id INTO my_file_id;

 INSERT INTO production.geneset (file_id,usr_id,cur_id,sp_id,gs_threshold_type,
   gs_threshold,gs_groups,gs_created,gs_updated,
   gs_status,gs_count,gs_uri,gs_gene_id_type,
   gs_name,gs_abbreviation,gs_description,gs_attribution)
   VALUES (my_file_id,my_usr_id,my_cur_id,my_sp_id,my_gs_threshold_type,
   my_gs_threshold,my_gs_groups,NOW(),NOW(),
   my_gs_status,my_gs_count,my_gs_uri,my_gs_gene_id_type,
   my_gs_name,my_gs_abbreviation,my_gs_description,my_gs_attribution)
   RETURNING gs_id INTO my_gs_id;

 RETURN my_gs_id;
END;$function$