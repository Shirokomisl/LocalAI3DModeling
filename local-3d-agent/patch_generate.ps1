$p='C:\AI\local-3d-agent\scripts\generate.py'
$s=[IO.File]::ReadAllText($p)
$old=@'
    candidate=(dist<30).astype(np.uint8)
    flood=np.zeros((h+2,w+2),np.uint8)
    cv2.floodFill(candidate,flood,(0,0),2)
    alpha[candidate==2]=0
'@
$new=@'
    candidate=(dist<30).astype(np.uint8)
    nbg,lab,stats,_=cv2.connectedComponentsWithStats(candidate,8)
    for i in range(1,nbg):
        x,y,ww,hh,area=stats[i]
        touches=(x==0 or y==0 or x+ww>=w or y+hh>=h)
        if touches:
            alpha[lab==i]=0
'@
if(!$s.Contains($old)){throw 'target not found'}
[IO.File]::WriteAllText($p,$s.Replace($old,$new),[Text.Encoding]::UTF8)
