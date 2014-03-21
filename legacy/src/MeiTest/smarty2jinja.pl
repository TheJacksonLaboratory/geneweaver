#!/usr/bin/perl
sub rtrim($) {
  my $string = shift;
  $string =~ s/\s+$//;
  return $string;
}
@lines=(<>);
for (@lines) {
  s/{if \$(.*?)}/{% if \1 %}/g;
  s/{elseif \$(.*?)}/{% elif \1 %}/g;
  s/{if !\$(.*?)}/{% if not \1 %}/g;
  s/{\$(.*?)}/{{ \1 }}/g;
  s/{else}/{% else %}/g;
  s/{\/if}/{% endif %}/g;
  s/truncate:"(\d*)"/truncate(\1)/g;
  s/truncate:(\d*)/truncate(\1)/g;
  s/(date_format|number_format):"(.*?)"/\1("\2")/g;
  s/strip_tags/striptags/g;
  s/{include file="(.*?).tpl"}/{% include "\1.html" %}/g;
  s/{include file=(.*?)}/{% include \1 %}/g;
  s/"\/(images|imagenes|pix|img|imgs|css|js)\//"\/static\/\1\//g;
  s/{section(.*?)max=(.*?)}/{section\1}{% if loop.index > \2 %}{% break %}{% endif %}/;
  $str .= $_;
}
while($str =~ m/{section name=(.*?) loop=\$(.*?)}/) {
  $loop = rtrim($2);
  $var = rtrim($1);
  $str =~ s/$loop\[$var\]/row/g;
  $str =~ s/{section name=(.*?) loop=\$(.*?)}/{% for row in \2 %}/;
  $str =~ s/{\/section}/{% endfor %}/;
}
print $str;
