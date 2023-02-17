
def find_yaml_info(entry_number: int, info: map) -> map:
    if info is None:
        return None

    for key, entry in info.items():
        if int(key) == entry_number:
            return entry
    return None

def parse_range_string(sequence: str, min_val: int, max_val: int) -> set:
    # Empty strings are not valid
    if sequence is None or len(sequence) == 0:
        return None

    # Make sure there are only valid characters
    valid_chars = '1234567890,- '
    v = sequence.strip(valid_chars)
    if len(v) != 0:
        return None

    # Strip whitespace
    sequence = sequence.strip(' ')

    r = []
    for seg in sequence.split(","):
        nums = seg.split("-")
        for v in nums:
            if len(v) == 0:
                return None
            v = int(v)
            if v < min_val or v > max_val:
                return None
        if len(nums) == 1:
            r.append(int(nums[0]))
        elif len(nums) == 2:
            for i in range(int(nums[0]), int(nums[1]) + 1):
                r.append(i)
        else:
            return None

    if len(r) == 0:
        return None

    return sorted(set(r))

def generate_range_string(seq: set) -> str:
    if len(seq) == 0:
        return None
    l = list(seq)
    if len(seq) == 1:
        return str(l[0])

    result = ""
    l.sort()
    end = start = l[0]
    for i in l[1:]:
        if i == (end + 1):
            end = i
        else:
            if start == end:
                result += f"{start},"
            else:
                result += f"{start}-{end},"
            start = end = i

    if start == end:
        result += f"{start}"
    else:
        result += f"{start}-{end}"
    start = end = i
    return result
