-- Narrow file bridge. Loaded BEFORE DCS sanitization; does not expose io/lfs/os.
-- Only fixed SQE-Live directories and validated filename tokens are accessible.
local FS={}
local lfs=lfs or require("lfs")
local open, rename, remove = io.open, os.rename, os.remove
local mkdir, attributes, dir = lfs.mkdir, lfs.attributes, lfs.dir
local wall_time, cpu_clock = os.time, os.clock
local MAX_SAVE, MAX_STATUS, MAX_COMMAND = 4*1024*1024, 512*1024, 8192
local function token(id)
    return type(id)=="string" and #id>=1 and #id<=80 and id:match("^[A-Za-z0-9_-]+$")~=nil
end
function FS.new(root)
    assert(type(root)=="string" and #root>0)
    root=root:gsub("\\","/"):gsub("/+$","").."/"
    mkdir(root);mkdir(root.."campaigns");mkdir(root.."commands")
    local function read(path,limit)
        local a=attributes(path)
        if not a then return nil,"missing" end
        if a.mode~="file" or a.size>limit then return nil,"file too large or not regular" end
        local f,err=open(path,"rb");if not f then return nil,err end
        local s=f:read(limit+1);f:close()
        if not s or #s>limit then return nil,"read limit exceeded" end
        return s
    end
    local function write(path,text,limit,backup,rotation)
        if type(text)~="string" or #text>limit then return false,"write limit exceeded" end
        local tmp=path..".tmp"
        local f,err=open(tmp,"wb");if not f then return false,err end
        local written,werr=f:write(text);local closed,cerr=f:close()
        if not written or not closed then remove(tmp);return false,werr or cerr end
        local had=attributes(path)~=nil
        local previous=path..(rotation or ".prev")
        if had then
            remove(previous)
            local ok,e=rename(path,previous)
            if not ok then remove(tmp);return false,"cannot rotate existing file: "..tostring(e) end
        end
        local ok,e=rename(tmp,path)
        if not ok then
            if had then rename(previous,path) end
            remove(tmp);return false,"cannot replace file: "..tostring(e)
        end
        if not backup then remove(previous) end
        return true
    end
    local api={}
    local session_serial=0
    function api.now() return wall_time() end
    function api.session()
        session_serial=session_serial+1
        return tostring(wall_time()).."-"..tostring(math.floor(cpu_clock()*1000000)).."-"..session_serial
    end
    function api.load(id,previous)
        if not token(id) then return nil,"invalid campaign id" end
        return read(root.."campaigns/"..id..".json"..(previous and ".prev" or ""),MAX_SAVE)
    end
    function api.save(id,text)
        if not token(id) then return false,"invalid campaign id" end
        return write(root.."campaigns/"..id..".json",text,MAX_SAVE,true)
    end
    function api.restore_previous(id,text)
        if not token(id) then return false,"invalid campaign id" end
        -- Never rotate a corrupt primary over the last known-good .prev checkpoint.
        return write(root.."campaigns/"..id..".json",text,MAX_SAVE,true,".invalid")
    end
    function api.publish(text) return write(root.."status.json",text,MAX_STATUS,false) end
    function api.status() return read(root.."status.json",MAX_STATUS) end
    function api.report(kind,text)
        if kind~="runtime" and kind~="ui" then return false,"invalid report kind" end
        return write(root.."diagnostics-"..kind..".json",text,128*1024,false)
    end
    function api.read_report(kind)
        if kind~="runtime" and kind~="ui" then return nil,"invalid report kind" end
        return read(root.."diagnostics-"..kind..".json",128*1024)
    end
    function api.enqueue(id,text)
        if not token(id) then return false,"invalid command id" end
        return write(root.."commands/cmd_"..id..".json",text,MAX_COMMAND,false)
    end
    function api.commands()
        local names={}
        for name in dir(root.."commands") do
            local id=name:match("^cmd_([A-Za-z0-9_-]+)%.json$")
            if id and token(id) then names[#names+1]=id end
        end
        table.sort(names)
        local out={}
        for i=1,math.min(#names,16) do
            local s,e=read(root.."commands/cmd_"..names[i]..".json",MAX_COMMAND)
            out[#out+1]={id=names[i],text=s,error=e}
        end
        return out
    end
    function api.ack(id)
        if not token(id) then return false end
        return remove(root.."commands/cmd_"..id..".json")
    end
    return api
end
return FS
