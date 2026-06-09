# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

args=commandArgs(trailingOnly=TRUE)


substrRight <- function(x, n){
  substr(x, nchar(x)-n+1, nchar(x))
}

gene.list.randomization = function(your.list, list.of.interest, background, B) { 
  stopifnot(is.numeric(B))


  interest.short=substrRight(interestfile, 30)

  your.list.length = length(your.list)
  your.list.unique = as.vector(unique(your.list), mode = "character")
  background = as.vector(background, mode = "character")
  background.length = length(background)
  your.list.unique.length = length(your.list.unique)
  C = length(your.list.unique)
  match.your.list = your.list.unique[which(!is.na(match(x = your.list.unique, table = list.of.interest)))]
  n.your.list = length(match.your.list)
  randomization.number = B
  randomization.number2 = B

  list.of.interest.length = length(list.of.interest)

  background.unique = unique(background)
  background.match = background.unique[which(!is.na(match(x = background.unique, table = list.of.interest)))]
  background.match.length = length(background.match)
  background.unique.length = length(background.unique)
  baseline = background.match.length/background.unique.length
  baseline.percent = baseline * 100
  enrichment = n.your.list/your.list.unique.length
  fold.enrichment = enrichment/baseline
  enrichment.percent = enrichment * 100

  random.gene.ns = vector(length = B, mode = "numeric")
  unique.n = vector (length = B, mode = "numeric")
  check.n = vector (length = B, mode = "numeric")
  check.unique.n = vector (length = B, mode = "numeric")
  enrich.vector = vector (length = B, mode = "numeric")
  random.enrich.vector = vector (length = B, mode = "numeric")

  for(i in 1:B) {
    r.list.unique = as.vector(sample(background, size = 2*C, replace = F))
    check.length = length(r.list.unique)
    r.list.unique2 = unique(r.list.unique, fromLast = FALSE)
    r.list.unique2.length = length(r.list.unique2)
    r.list.unique.short = r.list.unique2[1:C]
    n.r.list = length(which(!is.na(match(x = r.list.unique.short, table = list.of.interest))))
    enrich = n.r.list/your.list.unique.length
    enrich2 = enrich/baseline
    random.enrich.vector[i] = enrich
    enrich.vector[i] = enrich2
    length.unique = length(r.list.unique.short)
    check.unique.n[i] = r.list.unique2.length
    unique.n[i] = length.unique
    random.gene.ns[i] = n.r.list
    check.n[i] = check.length
    
      
      if(n.r.list < n.your.list) {
      randomization.number = (randomization.number - 1)
    } else {
      randomization.number = randomization.number
    }
  }

  
  mean.random.enrich = mean(random.enrich.vector) * 100
  mean.check = mean(check.n)
  mean.unique = mean(unique.n)
  mean.check.unique = mean(check.unique.n)
  mean.enrich = mean(enrich.vector)
  relative.enrich = fold.enrichment/mean.enrich
  mean.interest = mean(random.gene.ns)
  r.p.value = randomization.number / B
  relative.enrich.p = randomization.number2 / B
  

if(n.your.list<=max(random.gene.ns))
    if(n.your.list>0&&n.your.list<300&&r.p.value>0.0001){
        write(paste("pass",sep=""),file="")
        #write(paste(n.your.list, " ", r.p.value, sep = ""), file="")
    }else{
        write(paste("fail",sep=""),file="")
    }
}





#write.table(list.of.interest, file="listofinterest_check.txt", quote=F, row.names=FALSE, col.names=FALSE, sep="\t")
conn<-file(args[1],open="r")
your.list = readLines(conn)
close(conn)

background = your.list

files=args[2]
z=length(files)




U = as.integer(args[3])

B = as.integer(args[4])

u = your.list
short = u[1:U]
t = short
accession = gsub(pattern = "---", replacement = "0", x=t)
a = accession
indices = which(a != "0")
removed = a[indices]
removed2 = unique(removed)
your.list = removed2


q=ceiling(sqrt(z))
par(mfcol = c(q,q))


for(i in 1:z) {
interestfile=files[i]
list.of.interest = scan(files[i], what=character(), quiet=TRUE)
t = list.of.interest
accession = gsub(pattern = "---", replacement = "0", x=t)
a = accession
indices = which(a != "0")
removed = a[indices]
removed2 = unique(removed)
list.of.interest = removed2
gene.list.randomization(your.list, list.of.interest, background, B)
}

