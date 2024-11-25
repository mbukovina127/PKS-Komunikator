-- Define a custom protocol atop UDP
local p_custom = Proto("customproto", "Custom Protocol over UDP")

-- Define protocol fields
local f_flag = ProtoField.uint8("customproto.flag", "Flag", base.DEC)
local f_seq_num = ProtoField.uint32("customproto.seq_num", "Sequence Number", base.DEC)
local f_data = ProtoField.bytes("customproto.data", "Data")
local f_checksum = ProtoField.uint16("customproto.checksum", "Checksum", base.HEX)

-- Add fields to the protocol
p_custom.fields = { f_flag, f_seq_num, f_data, f_checksum }


--  SYN = 1
--  ACK = 2
--  KEEP_ALIVE = 3
--  FIN = 4
--  STR = 5
--  FRAG = 6
--  FRAG_F = 7
--  MSG = 11
--  MSG_F = 12

local flag_meanings = {
    [1] = "SYN",
    [2] = "ACK",
    [3] = "KEEP_ALIVE",
    [4] = "FIN",
    [5] = "STR",
    [6] = "FRAG",
    [7] = "FRAG_F",
    [11] = "MSG",
    [12] = "MSG_F",
    [13] = "KEEP_ALIVE_ACK"
    -- Add more flag mappings here as needed
}
-- Dissector function
function p_custom.dissector(buffer, pinfo, tree)
    -- Check packet length
    local pkt_len = buffer:len()
    if pkt_len < 7 then
        return -- Not enough data for the custom protocol
    end

    pinfo.cols.protocol = "Bukovina"

    -- Create protocol tree
    local subtree = tree:add(p_custom, buffer(), "Custom Protocol Data")

    -- Extract fields
    local flag = buffer(0, 1) -- First byte
    local seq_num = buffer(1, 4) -- Next 4 bytes
    local data_length = pkt_len - 7 -- Calculate data length excluding flag, seq_num, and checksum
    local data = buffer(5, data_length) -- Data field
    local checksum = buffer(pkt_len - 2, 2) -- Last 2 bytes for checksum

    local flag_value = flag:uint()
    local flag_description = flag_meanings[flag_value] or "Unknown"

    -- Add fields to the protocol tree
    subtree:add(f_flag, flag):append_text(" (" .. flag_description .. ")")
    subtree:add(f_seq_num, seq_num)
    subtree:add(f_data, data)
    subtree:add(f_checksum, checksum)

    -- Display info in the protocol column
    pinfo.cols.info = string.format("Flag: %d, Seq: %d, Data Len: %d", flag:uint(), seq_num:uint(), data_length)
end

-- Register protocol
p_custom:register_heuristic("udp", p_custom.dissector)
