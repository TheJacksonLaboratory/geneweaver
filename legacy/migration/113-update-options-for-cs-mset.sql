UPDATE odestatic.tool_param SET tp_visible = 'f' WHERE tp_name = any (array['MSET_Background','MSET_Species']);
UPDATE odestatic.tool_param SET tp_default = 5000 WHERE tp_name = 'MSET_NumberofSamples';
UPDATE odestatic.tool_param SET tp_options = '["5000", "10000", "15000", "30000"]' WHERE tp_name = 'MSET_NumberofSamples';