<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>ShowJocax</title>
</head>
    
<body>
<?php
//$pasta = __DIR__ . DIRECTORY_SEPARATOR ."fotosjocax"; 

$files = glob("fotosjocax/*.*");
for ($i=1; $i<count($files); $i++) { 
	$num = $files[$i]; 
	echo "<br>$num<br>";
	echo '<img   src="'.$num.'" />'; 
	//echo '<img  height="500" width="500" src="'.$num.'" />'; 
}

exit;
//======================================================
$files = glob("fotosjocax/*.*");
for ($i=1; $i<count($files); $i++) { 
	$num = $files[$i]; 
	echo '	<li--><img alt="random image" src="'.$num.'" />'; 
}
exit;
//====================================

$pasta = __DIR__ . DIRECTORY_SEPARATOR ."fotosjocax"; 
//echo "<br>$pasta<br>";

$arquivos = glob("$pasta{*.jpg,*.jpg,*.JPG,*.png,*.gif,}", GLOB_BRACE);
$arquivos = glob("$pasta"."."."*.jpg", GLOB_BRACE);
$arquivos = "C:\\inetpub\\wwwroot\\SibixWeb\\fotosjocax\\*.jpg";
$arquivos = "C:\\inetpub\\wwwroot\\SibixWeb\\fotosjocax\\*.jpg";
var_dump( $arquivos ); // exit;

//foreach($arquivos as $id => $img){
foreach(glob($arquivos) as $img){
   //echo "<br>".$img;//exit;
   echo '<div class="column is-4">
    <div class="card"> '. $img . '</div>
  </div>';
}
?>




</body>
</html>
