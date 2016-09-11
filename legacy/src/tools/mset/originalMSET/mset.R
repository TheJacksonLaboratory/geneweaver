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




substrRight <- function(x, n){
  substr(x, nchar(x)-n+1, nchar(x))
}

gene.list.randomization = function(your.list, list.of.interest, background, B) { 
  stopifnot(is.numeric(B))


  results.short=substrRight(resultsfile, 30)
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
  
if(n.your.list>max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (n.your.list+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

if(n.your.list<=max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (max(random.gene.ns)+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

  abline(v=n.your.list, col=4)

  write("", file="")
  write(paste("INPUT FILES", sep = ""), file="")
  write("Expression data file:", file="")
  write(paste(resultsfile, sep = ""), file="")
  write(paste(your.list.unique.length, " unique gene IDs in top ", U, " microarray results.", sep = ""), file="")
  write(paste(background.length, " gene IDs in microarray background.", sep = ""), file="")
  write("", file="")  

  write("Database of genes of interest file:", file="") 
  write(paste(interestfile, sep = ""), file="")
  write(paste(list.of.interest.length, " unique gene IDs in gene list of interest.", sep = ""), file="")
  write("", file="")  

  write(paste("RESULTS", sep = ""), file="")
  write(paste(B, " simulated results of length ", mean.unique, " generated from background.", sep = ""), file="")
  write(paste(n.your.list, " matches to database found in microarray results.", sep = ""), file="")
  write(paste(mean.interest, " mean matches to database in simulated results.", sep = ""), file="")
  write(paste(randomization.number, " simulated results of length ", your.list.length, 
              " contained at least as many matches 
to database as the actual expression results.", sep = ""), file="")
  write("", file="") 
  write(paste("p-value: ", signif(r.p.value, digits = 4), sep = ""), file="")
  write("", file="")  
  write(paste("ADDITIONAL INFO", sep = ""), file="")
  write(paste(signif(enrichment.percent, digits = 2), "% of top selected expression results are matches to database.", sep = ""), file="")
  write(paste(signif(baseline.percent, digits = 2), "% of background genes are matches to database.", sep = ""), file="")
  write(paste(signif(fold.enrichment, digits = 3), " fold enrichment of microarray results over background.", sep = ""), file="")
  write("", file="")
  write(paste("MATCHES TO DATABASE", sep = ""), file="")
  write(paste("Matches to database in top selected expression results:"), file="")
  write("", file="") 
  write(paste(match.your.list), file="")
  write("============================================================================", file="")

}


# Input file prompt interface
require(tcltk)




#write.table(list.of.interest, file="listofinterest_check.txt", quote=F, row.names=FALSE, col.names=FALSE, sep="\t")

tkmessageBox(message="Select all expression results, in order of significance, as a single column text file with no header.  Enrichment for gene sets of interest will be assessed within these results.")
expression=if(interactive()) tk_choose.files(caption="Select expression data.")
your.list = scan(expression, what=character(), quiet=TRUE)
resultsfile=expression

#your.list=scan(resultsfile<-tclvalue(tkgetOpenFile()), what=character(), quiet=TRUE)
background = your.list

tkmessageBox(message="Select one or more databases of genes of interest (e.g., disease/disorder associated gene list) as a single column text file with no header.  Enrichment of these sets will be evaluated within expression data.")
files=if(interactive()) tk_choose.files(caption="Select database(s) of genes of interest")

z=length(files)




repeat {
cat(sep="", "Enter how many of your top microarray results you would like to test 
for enrichment ('1000' for the top 1000, '2000' for the top 2000, etc.)
")
U = scan(what=numeric(), nmax = 1, quiet = TRUE)
break
}

repeat {
cat(sep="", "Enter the number of simulated results to generate (1000, 5000, 10000, etc.)
")
B = scan(what=numeric(), nmax = 1, quiet = TRUE)
break
}

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
dev.new(width=12, height=6)
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

