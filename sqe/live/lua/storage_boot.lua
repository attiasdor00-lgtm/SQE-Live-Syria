-- Installed by Install-SQE-Live.ps1. Loaded before sanitizeModule in MissionScripting.lua.
-- Keep standard DCS io, os and lfs sanitization enabled.
do
    local ok,err=pcall(function()
        local factory=dofile(lfs.writedir().."Scripts/SQE-Live/storage.lua")
        SQE_LIVE_STORAGE=factory.new(lfs.writedir().."SQE-Live")
    end)
    if not ok and log and log.write then log.write("SQE-Live",log.ERROR,tostring(err)) end
end
