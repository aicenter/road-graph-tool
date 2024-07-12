#!/bin/bash

# File path to the config file
CONFIG_FILE="config.ini"

# Function to display usage information
function display_help {
    echo "Usage: $0 [tag] [input_file]"
    echo "  Tag: "
    echo "      -d       : Display OSM file"
    echo "      -i       : Display information about OSM file"
    echo "      -ie      : Display extended information about OSM file"
    echo "Usage: $0 [tag] [input_file] -o [output_file]"
    echo "  Tag: "
    echo "     -h/--help : Display this help message"
    echo "     -r       : Renumber object IDs in OSM file"
    echo "               (Requires specifying output file with '-o' tag)"
    echo "     -s       : Sort OSM file based on IDs"
    echo "               (Requires specifying output file with '-o' tag)"
    echo "Usage: $0 -f [input_file] [style_file_path]"
    echo "  Tag: "
    echo "     -f       : Import OSM file to PostgreSQL database using osm2pgsql with the specified style file"
    echo "               (Optional: specify style file path - default.lua is used otherwise)"
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

# Check if the script is called with -h/--help
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    display_help
fi

# Check if the correct number of arguments is provided
if [ $# -lt 2 ]; then
    echo "Error: Insufficient arguments. Use \"$0 -h/--help\" for hint."
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

# Get value of given key from the config file
get_config_value() {
    key=$1
    grep -E "^${key}" "$CONFIG_FILE" | sed -E "s/^[^=]*= *//"
}

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
        check_extension "$output_file"

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
        check_extension "$output_file"

        osmium sort "$file_name" -o "$output_file"
        ;;
    -f)
        if [ "$4"]; then
            style_file_path=$4
        fi
        input_file=$3
        style_file_path="resources/lua_styles/default.lua"
        db_username=$(get_config_value "username")
        db_host=$(get_config_value "db_host")
        db_name=$(get_config_value "db_name")
        db_server_port=$(get_config_value "db_server_port")
        osm2pgsql -d "$db_name" -U "$db_username" -W -H "$db_host" -P "$db_server_port" --output=flex -S "$style_file_path" "$input_file" -x
        ;;
    *)
        echo "Invalid tag. Use \"$0 -h/--help\" for hint."
        exit 1
        ;;
esac

exit 0
