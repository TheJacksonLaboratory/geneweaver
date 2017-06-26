ALTER TABLE production.usr ADD COLUMN is_guest boolean;
UPDATE production.usr SET is_guest = 'f';
ALTER TABLE production.usr ALTER COLUMN is_guest SET NOT NULL;
ALTER TABLE production.usr ALTER COLUMN is_guest SET DEFAULT FALSE;
