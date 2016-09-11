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

gene_list_randomization = function(your_list, list_of_interest, background, numSimulatedResults) { 
  stopifnot(is.numeric(numSimulatedResults))


  results.short=substrRight(resultsfile, 30)
  interest.short=substrRight(interestfile, 30)

  randomization.number = numSimulatedResults
  randomization.number2 = numSimulatedResults

  your_set = as.vector(unique(your_list), mode = "character")

# #include<algorithm> set_intersection(your_set.begin,your_set.end,...
  your_set_intersect = intersect(your_set,list_of_interest)

  your_set.length= length(your_set)
  your_set_intersect.length = length(your_set_intersect)


  background = as.vector(background, mode = "character")
  background_set = unique(background)
  background_intersect = intersect(background_set,list_of_interest)

  baseline = length(background_intersect)/length(background_set)
  enrichment = your_set_intersect.length/your_set.length
  fold.enrichment = enrichment/baseline

  random.gene.ns = vector(length = numSimulatedResults, mode = "numeric")#vector<double>
  unique.n = vector (length = numSimulatedResults, mode = "numeric")
  check.n = vector (length = numSimulatedResults, mode = "numeric")
  check.unique.n = vector (length = numSimulatedResults, mode = "numeric")#set<double>
  enrich.vector = vector (length = numSimulatedResults, mode = "numeric")
  random.enrich.vector = vector (length = numSimulatedResults, mode = "numeric")

  #R is 1 indexed same as
  #for(int i=1;i<numSimulatedResults;i++) {
  for(i in 1:numSimulatedResults) {
    r.list.unique = as.vector(sample(background, size = 2*your_set.length, replace = F))
    check.length = length(r.list.unique)
    r.list.unique2 = unique(r.list.unique, fromLast = FALSE)
    r.list.unique2.length = length(r.list.unique2)
    r.list.unique.short = r.list.unique2[1:your_set.length]
    n.r.list = length(which(!is.na(match(x = r.list.unique.short, table = list_of_interest))))
    enrich = n.r.list/your_set.length
    enrich2 = enrich/baseline
    random.enrich.vector[i] = enrich
    enrich.vector[i] = enrich2
    length.unique = length(r.list.unique.short)
    check.unique.n[i] = r.list.unique2.length
    unique.n[i] = length.unique
    random.gene.ns[i] = n.r.list
    check.n[i] = check.length
    
      
    if(n.r.list < your_set_intersect.length) {
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
  r.p.value = randomization.number / numSimulatedResults
  relative.enrich.p = randomization.number2 / numSimulatedResults
  
if(your_set_intersect.length>max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (your_set_intersect.length+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

if(your_set_intersect.length<=max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (max(random.gene.ns)+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

  abline(v=your_set_intersect.length, col=4)

  write("", file="")
  write(paste("INPUT FILES", sep = ""), file="")
  write("Expression data file:", file="")
  write(paste(resultsfile, sep = ""), file="")
  write(paste(your_set.length, " unique gene IDs in top ", U, " microarray results.", sep = ""), file="")
  write(paste(length(background), " gene IDs in microarray background.", sep = ""), file="")
  write("", file="")  

  write("Database of genes of interest file:", file="") 
  write(paste(interestfile, sep = ""), file="")
  write(paste(length(list_of_interest), " unique gene IDs in gene list_of_interest.", sep = ""), file="")
  write("", file="")  

  write(paste("RESULTS", sep = ""), file="")
  write(paste(numSimulatedResults, " simulated results of length ", mean.unique, " generated from background.", sep = ""), file="")
  write(paste(your_set_intersect.length, " matches to database found in microarray results.", sep = ""), file="")
  write(paste(mean.interest, " mean matches to database in simulated results.", sep = ""), file="")
  write(paste(randomization.number, " simulated results of length ", length(your_list), 
              " contained at least as many matches 
to database as the actual expression results.", sep = ""), file="")
  write("", file="") 
  write(paste("p-value: ", signif(r.p.value, digits = 4), sep = ""), file="")
  write("", file="")  
  write(paste("ADDITIONAL INFO", sep = ""), file="")
  write(paste(signif(enrichment*100, digits = 2), "% of top selected expression results are matches to database.", sep = ""), file="")
  write(paste(signif(baseline*100, digits = 2), "% of background genes are matches to database.", sep = ""), file="")
  write(paste(signif(fold.enrichment, digits = 3), " fold enrichment of microarray results over background.", sep = ""), file="")
  write("", file="")
  write(paste("MATCHES TO DATABASE", sep = ""), file="")
  write(paste("Matches to database in top selected expression results:"), file="")
  write("", file="") 
  write(paste(your_set_intersect), file="")
  write("============================================================================", file="")

}


# Input file prompt interface
require(tcltk)




#write.table(list_of_interest, file="listofinterest_check.txt", quote=F, row.names=FALSE, col.names=FALSE, sep="\t")

tkmessageBox(message="Select all expression results, in order of significance, as a single column text file with no header.  Enrichment for gene sets of interest will be assessed within these results.")
expression=if(interactive()) tk_choose.files(caption="Select expression data.")
your_list = scan(expression, what=character(), quiet=TRUE)
resultsfile=expression

#your_list=scan(resultsfile<-tclvalue(tkgetOpenFile()), what=character(), quiet=TRUE)
background = your_list

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
numSimulatedResults = scan(what=numeric(), nmax = 1, quiet = TRUE)
break
}

u = your_list
short = u[1:U]
t = short
accession = gsub(pattern = "---", replacement = "0", x=t)
a = accession
indices = which(a != "0")
removed = a[indices]
removed2 = unique(removed)
your_list = removed2


q=ceiling(sqrt(z))
dev.new(width=12, height=6)
par(mfcol = c(q,q))


for(i in 1:z) {
interestfile=files[i]
list_of_interest = scan(files[i], what=character(), quiet=TRUE)
t = list_of_interest
accession = gsub(pattern = "---", replacement = "0", x=t)
a = accession
indices = which(a != "0")
removed = a[indices]
removed2 = unique(removed)
list_of_interest = removed2
gene_list_randomization(your_list, list_of_interest, background, numSimulatedResults)
}

