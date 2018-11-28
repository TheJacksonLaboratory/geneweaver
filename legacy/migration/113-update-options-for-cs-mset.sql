UPDATE odestatic.tool_param
SET tp_visible = 'f'
WHERE tp_name = any (array['MSET_Background','MSET_Species', 'MSET_NumberofSamples']);

INSERT INTO odestatic.tool_param
VALUES
('MSET',
 'MSET_NumberofTrials',
 'Set number of trials to perform for enrichment test',
 '{html_options name=$p.tp_name values=$p.tp_options output=$p.tp_options selected=$p._cur_val}',
 5000,
 '["5000", "10000", "15000", "30000"]',
 'select',
 TRUE
 );