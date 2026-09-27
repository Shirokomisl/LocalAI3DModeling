param(
 [int]$Steps=75,
 [int]$Resolution=512,
 [int]$Chunks=20000,
 [double]$Guidance=5.0,
 [int]$Seed=42,
 [switch]$SkipVision,
 [switch]$SkipQA,
 [switch]$SmokeTest,
 [switch]$SkipTigon,
 [double]$MinimumQAScore=4.0,
 [int]$MaxTigonRetries=3,
 [double]$MinTigonImprovement=0.25,
 [int]$MaxControllerIterations=1
)
$ErrorActionPreference="Continue"
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$source=Join-Path $root "input\source.png"
$out=Join-Path $root "output"
$py="C:\AI\Hunyuan3D-2.1\.venv\Scripts\python.exe"
$tigonpy="C:\AI\TIGON\.venv-py310\Scripts\python.exe"
$blender="C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if(!(Test-Path $source)){throw "Put source image at $source"}
New-Item -ItemType Directory -Force $out|Out-Null
$vision=Join-Path $out "vision.json"

Write-Host "== 1/4 Vision: geometry analysis =="
if(!$SkipVision){
 & $py "$root\scripts\vision.py" $source $vision
 if($LASTEXITCODE -ne 0){Write-Warning "Vision failed; using empty plan."; '{}'|Set-Content $vision}
}else{Write-Host "Vision skipped."}

function Invoke-SV-Candidate {
 param([string]$Name,[int]$S,[int]$R,[int]$C,[double]$G,[int]$Seed)
 $dir=Join-Path $out $Name
 New-Item -ItemType Directory -Force $dir|Out-Null
 Write-Host ("== Generate " + $Name + ": Hunyuan steps=$S res=$R chunks=$C guidance=$G seed=$Seed ==")
 & $py "$root\scripts\generate.py" $source --output "$dir\raw.glb" --steps $S --resolution $R --chunks $C --guidance-scale $G --seed $Seed --vision-json $vision | ForEach-Object { Write-Host $_ }
 if($LASTEXITCODE -ne 0){Write-Warning "$Name generation failed.";return $false}
 Write-Host ("== Blender " + $Name + ": render 4 diagnostic views for QA ==")
 & $blender --background --python "$root\scripts\blender_post.py" -- "$dir\raw.glb" "$dir\model.glb" | ForEach-Object { Write-Host $_ }
 if($LASTEXITCODE -ne 0){Write-Warning "$Name Blender postprocess failed.";return $false}
 return $true
}

function Invoke-Tigon-Candidate {
 param([string]$Name,[int]$S,[double]$G,[int]$Seed,[string]$Prompt="")
 $dir=Join-Path $out $Name
 New-Item -ItemType Directory -Force $dir|Out-Null
 Write-Host ("== Generate " + $Name + ": TIGON steps=$S cfg=$G seed=$Seed ==")
 $env:ATTN_BACKEND="sdpa"
 $env:SPCONV_ALGO="native"
 $tigonArgs=@("--image",$source,"--output","$dir\raw.glb","--vision-json",$vision)
 if($Prompt -and $Prompt.Trim().Length -gt 0){$tigonArgs += @("--prompt",$Prompt)}
 $tigonArgs += @("--steps",$S,"--cfg",$G,"--seed",$Seed)
 & $tigonpy "C:\AI\TIGON\run_tigon.py" @tigonArgs | ForEach-Object { Write-Host $_ }
 if($LASTEXITCODE -ne 0){Write-Warning "$Name generation failed.";return $false}
 Write-Host ("== Blender " + $Name + ": render 4 diagnostic views for QA ==")
 & $blender --background --python "$root\scripts\blender_post.py" -- "$dir\raw.glb" "$dir\model.glb" | ForEach-Object { Write-Host $_ }
 if($LASTEXITCODE -ne 0){Write-Warning "$Name Blender postprocess failed.";return $false}
 return $true
}

function New-TigonRepairPrompt([string]$QaPath,[string]$PreviousName){
 if(!(Test-Path $QaPath)){return ""}
 try{$q=Get-Content $QaPath -Raw|ConvertFrom-Json}catch{return ""}
 $rp=$q.repair_plan
 if(!$rp){return ""}
 $lines=@(
  "Correct the defects found in the previous TIGON attempt.",
  "Do not change the identity, silhouette, pose or proportions unless QA explicitly requires it.",
  "PRIORITY: $($rp.priority)"
 )
 if($rp.instructions -and $rp.instructions.Count){
  $lines += "REPAIR:"
  foreach($x in $rp.instructions){$lines += "- $x"}
 }
 if($rp.preserve -and $rp.preserve.Count){
  $lines += "PRESERVE:"
  foreach($x in $rp.preserve){$lines += "- $x"}
 }
 if($rp.avoid -and $rp.avoid.Count){
  $lines += "AVOID:"
  foreach($x in $rp.avoid){$lines += "- $x"}
 }
 $lines += "This is a correction pass. Reconstruct the object from the original image; do not make a flat sheet, relief or thin extrusion."
 return ($lines -join [Environment]::NewLine)
}

function Invoke-ArchitectorController([string]$Stage,[string]$StatePath,[string]$DecisionPath){
 $controller=Join-Path $root "architector\controller.py"
 Write-Host "== Architector controller: $Stage =="
 & $py $controller $StatePath $Stage $DecisionPath | ForEach-Object { Write-Host $_ }
 if($LASTEXITCODE -ne 0 -or !(Test-Path $DecisionPath)){
  Write-Warning "Architector controller failed."
  return $null
 }
 try{return Get-Content $DecisionPath -Raw|ConvertFrom-Json}catch{
  Write-Warning "Architector returned invalid decision JSON."
  return $null
 }
}

function Get-Score([string]$Name){
 $q=Join-Path $out "$Name\qa.json"
 if(!$SkipQA){
  $d=Join-Path $out $Name
  $args=@($source,
    (Join-Path $d "model_preview_front.png"),
    (Join-Path $d "model_preview_left.png"),
    (Join-Path $d "model_preview_back.png"),
    (Join-Path $d "model_preview_right.png"))
  $args += $vision
  $args += $q
  if(!(Test-Path (Join-Path $d "model_preview_front.png")) -or
    !(Test-Path (Join-Path $d "model_preview_left.png")) -or
    !(Test-Path (Join-Path $d "model_preview_back.png")) -or
    !(Test-Path (Join-Path $d "model_preview_right.png"))){
   Write-Warning "$Name QA skipped: diagnostic renders are missing."
   return 0.0
  }
  $null=& $py "$root\scripts\qa.py" @args
  if(Test-Path $q){try{$j=Get-Content $q -Raw|ConvertFrom-Json;return [double]$j.overall}catch{}}
 }
 return 0.0
}

Write-Host "== 2/4 Candidate generation =="
Write-Host "No generated 2D multiview images are fed into any generator."
$candidates=@(
 @{n="sv_candidate_01";kind="hunyuan";s=$Steps;r=$Resolution;c=$Chunks;g=$Guidance;seed=$Seed+911},
 @{n="sv_candidate_02";kind="hunyuan";s=[Math]::Max(95,$Steps+20);r=$Resolution;c=24000;g=5.5;seed=$Seed+1777},
 @{n="sv_candidate_03";kind="hunyuan";s=[Math]::Max(120,$Steps+45);r=576;c=24000;g=6.0;seed=$Seed+7331}
)
if(!$SkipTigon){
 $candidates += @{n="tigon_candidate_01";kind="tigon";s=35;r=0;c=0;g=3.0;seed=$Seed+4242}
 $candidates += @{n="tigon_candidate_02";kind="tigon";s=35;r=0;c=0;g=3.0;seed=$Seed+5243}
 $candidates += @{n="tigon_candidate_03";kind="tigon";s=35;r=0;c=0;g=3.0;seed=$Seed+6244}
}
if($SmokeTest){
 $candidates=@($candidates | Where-Object {$_.n -eq "sv_candidate_01"})
 $SkipTigon=$true
 Write-Host "Smoke test enabled: running only the first Hunyuan candidate."
}

$best="";$bestScore=-1.0
$records=@()

foreach($x in $candidates){
 if($x.kind -eq "hunyuan"){
  $ok=Invoke-SV-Candidate $x.n $x.s $x.r $x.c $x.g $x.seed
 }else{
  $ok=Invoke-Tigon-Candidate $x.n $x.s $x.g $x.seed
 }
 if($ok){
  $score=Get-Score $x.n
  $records += [PSCustomObject]@{name=$x.n;kind=$x.kind;qa=$score}
  Write-Host ("$($x.n) QA overall = {0}" -f $score)
  if($score -gt $bestScore){$bestScore=$score;$best=$x.n}
 }
}

# Closed-loop TIGON correction is disabled for now: TIGON is sampled independently and QA selects the best candidate.
if($false -and !$SkipTigon){
 $tigonBase=$records | Where-Object {$_.kind -eq "tigon" -and $_.name -eq "tigon_candidate_01"} | Select-Object -First 1
 if($tigonBase){
  $previousName=$tigonBase.name
  $previousScore=[double]$tigonBase.qa
  for($attempt=1;$attempt -le $MaxTigonRetries;$attempt++){
   $previousQa=Join-Path $out "$previousName\qa.json"
   if(!(Test-Path $previousQa)){break}
   try{$pq=Get-Content $previousQa -Raw|ConvertFrom-Json}catch{break}
   $reason=[string]$pq.repair_plan.stop_reason
   $instructions=@($pq.repair_plan.instructions)
   if($reason -eq "good_enough" -or $reason -eq "insufficient_reference" -or $instructions.Count -eq 0){
    Write-Host "TIGON correction loop stopped: $reason"
    break
   }
   $repairPrompt=New-TigonRepairPrompt $previousQa $previousName
   if([string]::IsNullOrWhiteSpace($repairPrompt)){break}
   $name="tigon_retry_{0:D2}" -f $attempt
   $retrySeed=$Seed+4242+($attempt*1001)
   Write-Host "== TIGON correction attempt $attempt/$MaxTigonRetries from $previousName =="
   $ok=Invoke-Tigon-Candidate $name 35 3.0 $retrySeed $repairPrompt
   if(!$ok){Write-Warning "TIGON correction attempt failed.";break}
   $score=Get-Score $name
   $records += [PSCustomObject]@{name=$name;kind="tigon_retry";qa=$score;attempt=$attempt;parent=$previousName}
   Write-Host ("$name QA overall = {0}; previous TIGON = {1}" -f $score,$previousScore)
   if($score -gt $bestScore){$bestScore=$score;$best=$name}
   $improvement=$score-$previousScore
   if($improvement -lt $MinTigonImprovement){
    Write-Host ("TIGON correction stopped: improvement {0} < required {1}." -f $improvement,$MinTigonImprovement)
    break
   }
   $previousName=$name
   $previousScore=$score
  }
 }
}

$controllerState=Join-Path $out "controller_state.json"
$controllerDecision=Join-Path $out "controller_decision.json"
$qaRecords=@()
foreach($rec in $records){
 $qp=Join-Path $out "$($rec.name)\qa.json"
 if(!$SkipQA -and (Test-Path $qp)){
  try{$qa=Get-Content $qp -Raw|ConvertFrom-Json}catch{$qa=$null}
  $qaRecords += [PSCustomObject]@{name=$rec.name;kind=$rec.kind;score=[double]$rec.qa;qa=$qa}
 }
}
$visionData=@{}
try{$visionData=Get-Content $vision -Raw|ConvertFrom-Json}catch{}
$state=[ordered]@{
 reference="input/source.png"
 stage="post_candidate_qa"
 iteration=1
 best_model=$best
 best_score=$bestScore
 vision=$visionData
 candidates=$qaRecords
 failed_strategies=@()
}
$state | ConvertTo-Json -Depth 12 | Set-Content $controllerState -Encoding UTF8
$decision=$null
if(!$SkipQA){
 $decision=Invoke-ArchitectorController "post_candidate_qa" $controllerState $controllerDecision
}else{
 Write-Host "Architector controller skipped: QA is disabled."
}
if($decision){
 Write-Host ("ARCHITECTOR: action={0}; generator={1}; confidence={2}" -f $decision.action,$decision.generator,$decision.confidence)
 if($decision.action -eq "retry_tigon" -or $decision.action -eq "generate_tigon"){
  $name="arch_tigon_{0:D2}" -f $MaxControllerIterations
  $prompt=[string]$decision.prompt
  $ok=Invoke-Tigon-Candidate $name 35 3.0 ($Seed+9000+$MaxControllerIterations) $prompt
  if($ok){
   $score=Get-Score $name
   $records += [PSCustomObject]@{name=$name;kind="architector_tigon";qa=$score}
   Write-Host ("$name QA overall = {0}" -f $score)
   if($score -gt $bestScore){$bestScore=$score;$best=$name}
  }
 }elseif($decision.action -eq "generate_hunyuan"){
  $name="arch_hunyuan_{0:D2}" -f $MaxControllerIterations
  $s=[int]$decision.steps
  if($s -le 0){$s=[Math]::Max(110,$Steps+35)}
  $r=[int]$decision.resolution
  if($r -le 0){$r=576}
  if($r -gt 576){Write-Warning "Architector resolution $r exceeds the 12 GB preset; clamping to 576.";$r=576}
  $g=[double]$decision.guidance_scale
  if($g -le 0){$g=5.8}
  $seed2=$Seed+[int]$decision.seed_offset+9000+$MaxControllerIterations
  $dir=Join-Path $out $name
  New-Item -ItemType Directory -Force $dir|Out-Null
  & $py "$root\scripts\generate.py" $source --output "$dir\raw.glb" --steps $s --resolution $r --chunks 24000 --guidance-scale $g --seed $seed2 --vision-json $vision
  if($LASTEXITCODE -eq 0){
   & $blender --background --python "$root\scripts\blender_post.py" -- "$dir\raw.glb" "$dir\model.glb"
   if($LASTEXITCODE -eq 0){
    $score=Get-Score $name
    $records += [PSCustomObject]@{name=$name;kind="architector_hunyuan";qa=$score}
    Write-Host ("$name QA overall = {0}" -f $score)
    if($score -gt $bestScore){$bestScore=$score;$best=$name}
   }
  }
 }
}

Write-Host "== 3/4 Select using deterministic multi-view QA =="
if(!$best){throw "All candidates failed."}
if(!$SkipQA -and $bestScore -lt $MinimumQAScore){
 throw "Best QA score $bestScore is below the minimum $MinimumQAScore; refusing to finalize."
}
Write-Host ("SELECTED BY QA: {0} QA={1}" -f $best,$bestScore)

$summary=[ordered]@{
 selected=$best
 selected_score=$bestScore
 candidates=$records
 tigon_used=(!$SkipTigon)
}
$summary | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out "selection.json") -Encoding UTF8

Write-Host "== 4/4 Finalize =="
$chosenDir=Join-Path $out $best
Get-ChildItem $chosenDir -File|ForEach-Object{
 Copy-Item $_.FullName (Join-Path $out $_.Name) -Force
}
Write-Host "DONE: $out\model.glb"
Write-Host "Selected candidate: $best"
Write-Host "QA: $bestScore"
Write-Host "IMPORTANT: rendered QA views are never used as generator input."
