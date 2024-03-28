#!/bin/bash

# Function to display usage information
function display_help {
    echo "Usage: $0 [tag] [input_file] [option]"
    echo "Tag: "
    echo "  -id                    : Filter geographic objects based on ID"
    echo "  -b                     : Filter geographic objects based on bounding box (with osm2pgsql)"
    echo "  -bos                   : Filter geographic objects based on bounding box (with osmium)"
    echo "  -t [expression_file]   : Filter objects based on tags in expression_file"
    echo "  -h                     : Display this help message"
    echo "Option: "
    echo "  -s                     : Specify strategy type (optional for: -id, -b)"
    exit 0
}

# Function to check strategy type
function check_strategy {
    local strategy="$1"
    valid_strategies=("simple" "complete_ways" "smart")
    for valid_strategy in "${valid_strategies[@]}"; do
        if [ "$strategy" == "$valid_strategy" ]; then
            return 0
        fi
    done
    return 1
}

# Function to filter out based on input id
function extract_id {
    tmp_file="./extract/to-extract.osm"
    local relation_id="$1"
    local input_file="$2"
    local strategy="$3"
    local path="./extract/extract-id.geojson"
    curl -o "$tmp_file" "https://www.openstreetmap.org/api/0.6/relation/$relation_id/full"
    if [ -z "$strategy" ]; then
        osmium extract -c "$path" "$input_file"
    else
        osmium extract -c "$path" "$input_file" -s "$strategy"
    fi
    rm "$tmp_file"
}

# Function to extract based on bounding box with osm2pgsql
function extract_bbox_osm2pgsql {
    local relation_id="$1"
    local input_file="$2"

    tmp_file="to-extract.xml"
    curl -o "$tmp_file" "https://www.openstreetmap.org/api/0.6/relation/$relation_id/full"
    python3 find_bbox.py "$tmp_file" 
    rm "$tmp_file"
}

# Function to extract based on bounding box with osmium
function extract_bbox_osmium {
    local coords="$1"
    local input_file="$2"
    local strategy="$3"
    # should match four floats:
    local coords_regex='^[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?,[0-9]+(\.[0-9]+)?$'
    if [[ "$coords" =~ $coords_regex ]]; then
        if [ -z "$strategy" ]; then
            osmium extract -b "$coords" "$input_file" -o extracted-bbox.osm.pbf
        else
            osmium extract -b "$coords" "$input_file" -o extracted-bbox.osm.pbf -s "$strategy"
        fi
    else
        if [ -z "$strategy" ]; then
            osmium extract -c "$coords" "$input_file"
        else
            osmium extract -c "$coords" "$input_file" -s "$strategy"
        fi   
    fi
}

# Extracting arguments
tag=$1

if [ "$tag" == "-h" ]; then
    display_help
fi

# Run command based on provided tags
case "$tag" in
    -id)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: You need to specify relation ID and input file."
            exit 1
        fi
        relation_id="$2"
        input_file="$3"
        if [ "$4" == "-s" ]; then
            if [ -z "$5" ]; then
                echo "Error: Specify strategy type."
                exit 1
            fi
            if ! check_strategy_type "$5"; then
                echo "Error: Invalid strategy type. Call ./filter.sh -h to display help."
                exit 1
            fi
            extract_id "$relation_id" "$input_file" "$5"
        else
            extract_id "$relation_id" "$input_file"
        fi
        ;;
    -bos)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: You need to specify either coordinates or config file with coordinates and input file."
            exit 1
        fi

        if [ "$4" == "-s" ]; then
            if [ -z "$5" ]; then
                echo "Error: Specify strategy type."
                exit 1
            fi
            if ! check_strategy_type "$5"; then
                echo "Error: Invalid strategy type. Call ./filter.sh -h to display help."
                exit 1
            fi
            extract_bbox_osmium "$2" "$3" "$5"
        else
            extract_bbox_osmium "$2" "$3"
        fi
        ;;
    -b)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: You need to specify relation ID and input file."
            exit 1
        fi
        relation_id="$2"
        input_file="$3"
        extract_bbox_osm2pgsql "$relation_id" "$input_file"
        ;;
    -t)
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "Error: You need to specify expression file and input file."
            exit 1
        fi
        osmium tags-filter "$3" -e "$2" -o filtered.osm.pbf
        ;;
    *)
        echo "Invalid tag. Call ./filter.sh -h to display help."
        exit 1
        ;;
esac

exit 0
