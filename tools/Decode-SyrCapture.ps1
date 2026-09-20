<#
.SYNOPSIS
  Liest einen FRITZ!Box-Mitschnitt (.eth) und entschluesselt die Klartext-Kommunikation
  eines SYR Safe-T+ Connect mit iot1.syrconnect.de.

.BESCHREIBUNG DES PROTOKOLLS
  Transport : HTTP POST (unverschluesselt) an
              iot1.syrconnect.de/WebServices/SyrConnectDeviceWebService.asmx/GetAllCommands
              Body: xml=<sc><cp v="XXXX"/><dat v="NUTZLAST"/></sc>   (form-urlencoded)
  Nutzlast  : Klartext-XML  ->  XOR mit 1-Byte-Schluessel (wechselt pro Nachricht!)
              ->  7 "unsichere" Bytes werden durch Sonderzeichen ersetzt
              ->  UTF-8
  Escapes   : 0x22 "  -> AE    0x25 %  -> ae    0x26 &  -> UE    0x27 '  -> oe
              0x2B +  -> EUR   0x3C <  -> OE    0x3E >  -> ue
  Sonderfall: ergibt das XOR 0x7F (DEL), wird das Zeichen unveraendert uebertragen.
              Beim Entschluesseln heisst 0x7F also: nimm das gesendete Byte selbst.
  Schluessel: nicht aus cp ableitbar; hier ueber den bekannten Anfang "<d>" / "<sc>" bestimmt.

.BEISPIEL
  .\Decode-SyrCapture.ps1 -Path .\fritzbox-vcc0.eth
#>
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$ServerIp = '212.77.236.30'   # iot1.syrconnect.de
)

$esc=@{ 0x00C4=0x22; 0x00E4=0x25; 0x00DC=0x26; 0x00F6=0x27; 0x20AC=0x2B; 0x00D6=0x3C; 0x00FC=0x3E }
function BE16($a,$i){ return ([int]$a[$i] -shl 8) -bor [int]$a[$i+1] }

function Convert-SyrPayload([byte[]]$p){
  $cip=New-Object System.Collections.Generic.List[int]
  $j=0
  while($j -lt $p.Length){
    $b=[int]$p[$j]
    if($b -lt 0x80){ $cip.Add($b); $j++; continue }
    $cpv=-1
    if($b -ge 0xC2 -and $b -le 0xDF -and $j+1 -lt $p.Length){ $cpv=(($b -band 0x1F) -shl 6) -bor ([int]$p[$j+1] -band 0x3F); $j+=2 }
    elseif($b -ge 0xE0 -and $b -le 0xEF -and $j+2 -lt $p.Length){ $cpv=(($b -band 0x0F) -shl 12) -bor (([int]$p[$j+1] -band 0x3F) -shl 6) -bor ([int]$p[$j+2] -band 0x3F); $j+=3 }
    else { $cpv=$b; $j++ }
    if($esc.ContainsKey($cpv)){ $cip.Add($esc[$cpv]) } else { $cip.Add(0x3F) }
  }
  if($cip.Count -lt 4){ return $null }
  $key=-1
  for($k=0;$k -lt 256;$k++){
    $pre=-join (0..3 | % { $v=(($cip[$_]) -bxor $k) -band 0xFF; [char]$(if($v -eq 0x7F){$cip[$_]}else{$v}) })
    if($pre.StartsWith('<d><') -or $pre.StartsWith('<sc>')){ $key=$k; break }
  }
  if($key -lt 0){ return $null }
  $sb=New-Object System.Text.StringBuilder
  foreach($c in $cip){
    $v=($c -bxor $key) -band 0xFF
    # 0x7F markiert ein unveraendert uebertragenes Zeichen.
    [void]$sb.Append([char]$(if($v -eq 0x7F){$c}else{$v}))
  }
  return [pscustomobject]@{ Key=$key; Xml=$sb.ToString() }
}

# --- pcap lesen (AVM nutzt "modified pcap": 24-Byte-Recordheader, PPPoE-Frames) ---
$b=[System.IO.File]::ReadAllBytes($Path)
if([BitConverter]::ToUInt32($b,0) -ne 2712847156){ Write-Warning "Unerwartete Magic - evtl. anderes pcap-Format" }
$off=24; $streams=@{}
while ($off + 24 -le $b.Length) {
  $incl=[BitConverter]::ToUInt32($b,$off+8); $p=$off+24
  if ($incl -le 0 -or $p+$incl -gt $b.Length) { break }
  $end=$p+$incl; $et=BE16 $b ($p+12); $ipo=$p+14
  while ($et -eq 0x8100 -and $ipo+4 -lt $end) { $et=BE16 $b ($ipo+2); $ipo+=4 }
  if ($et -eq 0x8864 -and $ipo+8 -lt $end) { $pp=BE16 $b ($ipo+6); $ipo+=8; $et= if($pp -eq 0x21){0x0800}else{0} }
  if ($et -eq 0x0800 -and $ipo+20 -le $end) {
    $ihl=([int]$b[$ipo] -band 0x0F)*4
    if ([int]$b[$ipo+9] -eq 6) {
      $src="$($b[$ipo+12]).$($b[$ipo+13]).$($b[$ipo+14]).$($b[$ipo+15])"
      $dst="$($b[$ipo+16]).$($b[$ipo+17]).$($b[$ipo+18]).$($b[$ipo+19])"
      $ipend=[Math]::Min($ipo+(BE16 $b ($ipo+2)),$end); $tho=$ipo+$ihl
      if ($tho+20 -le $ipend) {
        $sp=BE16 $b $tho; $dp=BE16 $b ($tho+2)
        if (($sp -eq 80 -or $dp -eq 80) -and ($src -eq $ServerIp -or $dst -eq $ServerIp)) {
          $pl=$tho+(([int]$b[$tho+12] -shr 4)*4); $plen=$ipend-$pl
          if ($plen -gt 0) {
            $k = if($sp -eq 80){"$dp-Antwort"}else{"$sp-Anfrage"}
            if(-not $streams.ContainsKey($k)){ $streams[$k]=New-Object System.Collections.Generic.List[byte] }
            $streams[$k].AddRange([byte[]]$b[$pl..($ipend-1)])
          }
        }
      }
    }
  }
  $off=$p+$incl
}

foreach($k in ($streams.Keys | Sort-Object)){
  $bytes=[byte[]]$streams[$k].ToArray()
  $s=[System.Text.Encoding]::ASCII.GetString($bytes)
  $i=$s.IndexOf('dat v="'); if($i -lt 0){ continue }
  $st=$i+7; $e=$s.IndexOf('"',$st); if($e -lt 0){ continue }
  $r=Convert-SyrPayload $bytes[$st..($e-1)]
  $cp=[regex]::Match($s,'cp v="([^"]*)"').Groups[1].Value
  Write-Output ("=== {0}  |  cp={1}  |  Schluessel=0x{2:X2} ===" -f $k, $cp, $(if($r){$r.Key}else{0}))
  if($r){ Write-Output $r.Xml } else { Write-Output "(konnte nicht dekodiert werden)" }
  Write-Output ""
}
