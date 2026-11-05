-- Simulates widget/callback contracts, never the real dxgui renderer.
local U={widgets={},hotkeys={},visible=true}
local function widget(name,kind)
    local w={name=name,kind=kind,children={},skin={skinData={states={released={{}},pressed={{}},disabled={{}}}}},enabled=true,visible=true}
    U.widgets[#U.widgets+1]=w
    function w:setText(t) self.text=t end
    function w:getSkin()return self.skin end
    function w:setSkin(s)self.skin=s end
    function w:setVisible(v)self.visible=v end
    function w:setHasCursor(v)self.cursor=v end
    function w:setFocused(v)self.focus=v end
    function w:setEnabled(v)self.enabled=v end
    function w:setBounds(x,y,w,h)self.bounds={x,y,w,h}end
    function w:addMouseUpCallback(fn)self.click=fn end
    function w:addHotKeyCallback(key,fn)U.hotkeys[key]=fn end
    function w:insertWidget(child)self.children[#self.children+1]=child;child.parent=self end
    return w
end
local real_dofile=dofile
package.preload.lfs=function()return {writedir=function()return "/profile/" end}end
package.preload.Skin=function()return {windowSkinChatMin=function()return "hidden" end}end
package.preload.dxgui=function()return {GetScreenSize=function()return 1920,1080 end}end
package.preload.Panel=function()return {new=function()
    if U.fail_panel then error("injected native Panel failure") end
    return widget("dynamic panel","Panel")
end}end
package.preload.Button=function()return {new=function(text)
    local w=widget("dynamic button","Button");w.text=text;return w
end}end
package.preload.DialogLoader=function()return {
    spawnDialogFromFile=function(path)
        assert(path=="/profile/Scripts/SQE-Live/Operations.dlg")
        real_dofile(lua_path.."/Operations.dlg")
        U.window=widget("window","Window")
        for name,def in pairs(dialog.children)do
            local w=widget(name,def.type);local p=def.params;local b=p.bounds
            w:setBounds(b.x,b.y,b.w,b.h);w.text=p.text;w.visible=p.visible;w.enabled=p.enabled~=false
            if def.skin.states then w.skin.skinData=def.skin end
            U.window[name]=w;U.window:insertWidget(w)
        end
        return U.window
    end
}end
function U.sector(caption)
    for _,w in ipairs(U.window.MapCanvas.children) do
        if w.kind=="Button" and w.visible and w.text:find(caption,1,true) then return w end
    end
    error("Missing map node: "..caption)
end
dofile=function(path)
    local file=path:match("([^/]+)$")
    if file=="storage.lua" then return {new=function()return fs end}end
    return real_dofile(lua_path.."/"..file)
end
os.time=fs.now;os.clock=function()return mock.clock end
DCS={setUserCallbacks=function(h)U.handler=h end}
net={log=function(s)U.last_log=s end}
return U
