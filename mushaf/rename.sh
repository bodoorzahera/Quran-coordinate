#!/bin/bash

# Counter starts at 1
count=1

# Loop over all files matching page-*.json sorted numerically
for file in $(ls page-*.json | sort -V); do
    # Format the new name with leading zeros (3 digits)
    new_name=$(printf "Page%03d.json" "$count")
    
    # Rename the file
    mv "$file" "$new_name"
    
    # Increment counter
    count=$((count + 1))
done
