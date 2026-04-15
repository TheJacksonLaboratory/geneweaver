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

gene_list_randomization = function(topGenesSet, interestGeneSet, background, numSimulatedResults) { 
  stopifnot(is.numeric(numSimulatedResults))


  results.short=substrRight(resultsfile, 30)
  interest.short=substrRight(interestfile, 30)

  #holds the number of results where the intersect length of the simulated
  #results is greater than the intersect of the list of intrest with the top.
  #its initialized to assume every result is greater, then subtracts out the
  #ones that aren't
  numSimulatedGreater= numSimulatedResults
  randomization.number2 = numSimulatedResults

  topGenesSet = as.vector(unique(topGenesSet), mode = "character")

# #include<algorithm> set_intersection(topGenesSet.begin,topGenesSet.end,...
  topGenesSet_intersect = intersect(topGenesSet,interestGeneSet)

  topGenesSet.length= length(topGenesSet)
  topGenesSet_intersect.length = length(topGenesSet_intersect)


  background = as.vector(background, mode = "character")
  background_set = unique(background)
  background_intersect = intersect(background_set,interestGeneSet)

  baseline = length(background_intersect)/length(background_set)
  enrichment = topGenesSet_intersect.length/topGenesSet.length
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
    sampledList = as.vector(sample(background, size = 2*topGenesSet.length, replace = F))
    sampledList.length= length(sampledList)
    sampledSet = unique(sampledList, fromLast = FALSE)
    sampledSet.length = length(sampledSet)
    sampledSet = sampledSet[1:topGenesSet.length]#truncate to match length of topGenesSet

    sampledSet_intersect.length = length(intersect(sampledSet,interestGeneSet)) #TODO: clean this too
    #print(sampledSet_intersect.length)
    enrich = sampledSet_intersect.length/topGenesSet.length
    enrich2 = enrich/baseline
    random.enrich.vector[i] = enrich
    enrich.vector[i] = enrich2
    length.unique = length(sampledSet)
    check.unique.n[i] = sampledSet.length
    unique.n[i] = length.unique
    random.gene.ns[i] = sampledSet_intersect.length
    check.n[i] = sampledList.length
    
      # with list of interest
    if(sampledSet_intersect.length < topGenesSet_intersect.length) {
      numSimulatedGreater= (numSimulatedGreater- 1)#no -- in R but this is numSimulatedGreater--
    } 
  }

  
  mean.random.enrich = mean(random.enrich.vector) * 100
  mean.check = mean(check.n)
  mean.unique = mean(unique.n)
  mean.check.unique = mean(check.unique.n)
  mean.enrich = mean(enrich.vector)
  relative.enrich = fold.enrichment/mean.enrich
  mean.interest = mean(random.gene.ns)
  r.p.value = numSimulatedGreater/ numSimulatedResults
  relative.enrich.p = randomization.number2 / numSimulatedResults
  
if(topGenesSet_intersect.length>max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (topGenesSet_intersect.length+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

if(topGenesSet_intersect.length<=max(random.gene.ns))
plot(density(random.gene.ns), xlim=c(0, (max(random.gene.ns)+2)), main = "Probability density of simulations", ylab="Probability", xlab="Matches to database", sub=paste("Database: ...", interest.short))

  abline(v=topGenesSet_intersect.length, col=4)

  write("", file="")
  write(paste("INPUT FILES", sep = ""), file="")
  write("Expression data file:", file="")
  write(paste(resultsfile, sep = ""), file="")
  write(paste(topGenesSet.length, " unique gene IDs in top ", topListSize, " microarray results.", sep = ""), file="")
  write(paste(length(background), " gene IDs in microarray background.", sep = ""), file="")
  write("", file="")  

  write("Database of genes of interest file:", file="") 
  write(paste(interestfile, sep = ""), file="")
  write(paste(length(interestGeneSet), " unique gene IDs in gene interestGeneSet.", sep = ""), file="")
  write("", file="")  

  write(paste("RESULTS", sep = ""), file="")
  write(paste(numSimulatedResults, " simulated results of length ", mean.unique, " generated from background.", sep = ""), file="")
  write(paste(topGenesSet_intersect.length, " matches to database found in microarray results.", sep = ""), file="")
  write(paste(mean.interest, " mean matches to database in simulated results.", sep = ""), file="")
  write(paste(numSimulatedGreater, " simulated results of length ", length(topGenesSet), 
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
  write(paste(topGenesSet_intersect), file="")
  write("============================================================================", file="")

  write(paste(random.gene.ns), file="plotpoints")
}


# Input file prompt interface
require(tcltk)




#write.table(interestGeneSet, file="listofinterest_check.txt", quote=F, row.names=FALSE, col.names=FALSE, sep="\t")

tkmessageBox(message="Select all expression results, in order of significance, as a single column text file with no header.  Enrichment for gene sets of interest will be assessed within these results.")
expression=if(interactive()) tk_choose.files(caption="Select expression data.")
background = scan(expression, what=character(), quiet=TRUE)
resultsfile=expression


tkmessageBox(message="Select one or more databases of genes of interest (e.g., disease/disorder associated gene list) as a single column text file with no header.  Enrichment of these sets will be evaluated within expression data.")
files=if(interactive()) tk_choose.files(caption="Select database(s) of genes of interest")

numFiles=length(files)




repeat {
cat(sep="", "Enter how many of your top microarray results you would like to test 
for enrichment ('1000' for the top 1000, '2000' for the top 2000, etc.)
")
topListSize = scan(what=numeric(), nmax = 1, quiet = TRUE)
break
}

repeat {
cat(sep="", "Enter the number of simulated results to generate (1000, 5000, 10000, etc.)
")
numSimulatedResults = scan(what=numeric(), nmax = 1, quiet = TRUE)
break
}

indices = which(background!= "---")# indices where element of topGeneListDashes != ---
background= background[indices]# remove the ones that are ---

topGeneListDashes= background[1:topListSize] #get the top n rows from the 
topGenesSet = unique(topGeneListDashes)# to set


q=ceiling(sqrt(numFiles))
dev.new(width=12, height=6)
par(mfcol = c(q,q))


for(i in 1:numFiles) {
    interestfile=files[i]
    list_of_interest= scan(files[i], what=character(), quiet=TRUE)
    indices = which(list_of_interest != "---")#indices where the element of list_of_interest is not ---
    list_of_interestClean= list_of_interest[indices]# cut out all the --- entries
    interestGeneSet = unique(list_of_interestClean)# to set
    gene_list_randomization(topGenesSet, interestGeneSet, background, numSimulatedResults)
}

