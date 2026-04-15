#run all files of a certain type in a dir
#!/bin/bash
for f in *.py
do
   python "$f"
done