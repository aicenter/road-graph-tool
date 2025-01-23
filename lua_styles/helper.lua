-- Remove some of the tags and returns true if there are no tags left.
function clean_tags(tags)
	tags.odbl = nil
	tags.created_by = nil
	tags.source = nil
	tags["source:ref"] = nil

	return next(tags) == nil
end

-- Break down version into major, minor and patch
local function split_version(version)
    local major, minor, patch = version:match("(%d+)%.(%d+)%.(%d+)")
    return tonumber(major), tonumber(minor), tonumber(patch)
end

-- Return true if version v1 is greater than or equal to version v2 
function compare_version(v1, v2)
    local v1_ma, v1_mi, v1_p = split_version(v1)
    local v2_ma, v2_mi, v2_p = split_version(v2)
    if v1_ma > v2_ma then return true end
    if v1_ma < v2_ma then return false end

    if v1_mi > v2_mi then return true end
    if v1_mi < v2_mi then return false end

    return v1_p >= v2_p
end

return {
    clean_tags = clean_tags,
    compare_version = compare_version,
}