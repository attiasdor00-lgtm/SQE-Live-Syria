-- Native dxgui adapter. Fixed pools; map data/layout live in the pure map module.
-- Uses Panel/Button construction and skin APIs also used by dcs-scratchpad.
local U={};U.__index=U
local function copy(v)
    if type(v)~="table" then return v end
    local out={};for k,x in pairs(v) do out[k]=copy(x) end;return out
end
local function colour(seed,background,text)
    local skin=copy(seed)
    local data=skin.skinData or skin
    data.states=data.states or {};data.states.released=data.states.released or {{}}
    for _,layers in pairs(data.states) do
        for _,layer in ipairs(layers) do
            if background then layer.bkg=layer.bkg or {};layer.bkg.center_center=background end
            if text then
                layer.text=layer.text or {};layer.text.color=text
                layer.text.fontSize=12;layer.text.lineHeight=14
            end
        end
    end
    return skin
end
function U.new(canvas,button_skin,Panel,Button,M,on_sector)
    local self=setmetatable({nodes={},lines={},skins={}},U)
    local panel_skin=canvas:getSkin()
    self.skins.edge=colour(panel_skin,"0x526277ff")
    self.skins.front=colour(panel_skin,"0xf0bb55ff")
    self.skins.stale=colour(button_skin,"0x303944ff","0xa5afbcff")
    self.skins.blue=colour(button_skin,"0x123d5cff","0x79cdffff")
    self.skins.red=colour(button_skin,"0x562a32ff","0xffa2adff")
    self.skins.blue_selected=colour(button_skin,"0x225f86ff","0xffffffff")
    self.skins.red_selected=colour(button_skin,"0x86404cff","0xffffffff")
    for i=1,M.MAX_EDGES*3 do
        local line=Panel.new();line:setSkin(self.skins.edge);line:setEnabled(false);line:setVisible(false)
        canvas:insertWidget(line);self.lines[i]=line
    end
    for i=1,M.MAX_SECTORS do
        local button=Button.new("");button:setSkin(button_skin);button:setVisible(false)
        local node={widget=button,id=false};self.nodes[i]=node
        button:addMouseUpCallback(function()if node.id then on_sector(node.id) end end)
        canvas:insertWidget(button)
    end
    return self
end
function U:render(layout,online,selected,visible)
    local line_index=0
    for _,edge in ipairs(layout and layout.edges or {}) do
        for _,p in ipairs(edge.segments) do
            line_index=line_index+1;local line=self.lines[line_index]
            line:setBounds(p.x,p.y,p.w,p.h)
            line:setSkin(online and edge.front and self.skins.front or self.skins.edge)
            line:setVisible(visible)
        end
    end
    for i=line_index+1,#self.lines do self.lines[i]:setVisible(false) end
    for i,node in ipairs(self.nodes) do
        local n=layout and layout.nodes[i]
        node.id=n and n.id or false
        if n then
            local active=n.id==selected
            local caption=n.compact and (n.caption..(n.frontline and "*" or "")
                ..(#n.bases>0 and "B" or "")..(#n.farps>0 and "F" or ""))
                or (string.upper(n.owner).." "..n.caption..(n.frontline and " *" or "")
                    ..(#n.bases>0 and " [B]" or "")..(#n.farps>0 and " [F]" or ""))
            node.widget:setBounds(n.x,n.y,n.w,n.h)
            node.widget:setText(caption)
            node.widget:setSkin(not online and self.skins.stale or self.skins[n.owner..(active and "_selected" or "")])
            node.widget:setEnabled(online==true);node.widget:setVisible(visible)
        else node.widget:setVisible(false) end
    end
end
return U
