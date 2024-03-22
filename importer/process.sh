#!/bin/bash

# Function to display usage information
function display_help {
    echo "Usage: $0 [tag] [input_file]"
    echo "  Tag: "
    echo "      -d       : Display OSM file"
    echo "      -i       : Display information about OSM file"
    echo "Usage: $0 [tag] [input_file] -o [output_file]"
    echo "  Tag: "
    echo "      -r       : Renumber object IDs in OSM file"
    echo "               (Requires specifying output file with '-o' tag)"
    echo "      -s       : Sort OSM file based on IDs"
    echo "               (Requires specifying output file with '-o' tag)"
    echo "      -h       : Display this help message"
    exit 0
}

# Function to check if the file has a valid extension
function check_extension {
    file_name="$1"
    valid_extensions=("osm" "osm.pbf")
    valid_extension=false
    for ext in "${valid_extensions[@]}"; do
        if [[ "$file_name" == *".$ext" ]]; then
            valid_extension=true
            break
        fi
    done
    if ! $valid_extension; then
        echo "Error: File must have one of the following extensions: ${valid_extensions[@]/#/.}."
        exit 1
    fi
}

# Check if the script is called with -h
if [ "$1" == "-h" ]; then
    display_help
fi

# Check if the correct number of arguments is provided
if [ $# -lt 2 ]; then
    echo "Error: Insufficient arguments. Use \"$0 -h\" for hint."
    exit 1
fi

# Extracting arguments
tag=$1
file_name=$2

# Check if the file exists
if [ ! -e "$file_name" ]; then
    echo "Error: File '$file_name' does not exist."
    exit 1
fi

# Check the input file extension
check_extension "$file_name"

# Run command based on provided tag
case "$tag" in
    -d)
        osmium show "$file_name"
        ;;
    -i)
        osmium fileinfo -e "$file_name"
        ;;
    -r)
        if [ "$3" != "-o" ]; then
            echo "Error: An output file must be specified with '-o' tag."
            exit 1
        fi
        if [ $# -lt 4 ]; then
            echo "Error: Output file missing."
            exit 1
        fi
        output_file=$4
        # Check the output file extension
        # check_extension "$output_file"

        osmium renumber "$file_name" -o "$output_file"
        ;;
    -s)
        if [ "$3" != "-o" ]; then
            echo "Error: An output file must be specified with '-o' tag."
            exit 1
        fi
        if [ $# -lt 4 ]; then
            echo "Error: Output file missing."
            exit 1
        fi
        output_file=$4
        # Check the output file extension
        # check_extension "$output_file"

        osmium sort "$file_name" -o "$output_file"
        ;;
    *)
        echo "Invalid tag. Valid tags are: -d (display file), -i (info), -s (sort), -r (renumber), -h (help) ."
        exit 1
        ;;
esac

exit 0
