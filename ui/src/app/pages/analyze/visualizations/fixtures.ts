/**
 * Real tool outputs from dev (2026-10-07), trimmed to stay small.
 *
 * Gene sets: 167180, 378899, 164706, 379321, 233535 (public mouse; behaviour, GPCR,
 * neurotransmitter receptor, cAMP signalling); 400405 + 14923 for a JaccardSimilarity pair
 * with a p-value; MSET over 164706 + 167180. Shapes are exactly what the API returns.
 */
/* eslint-disable */
export const FIXTURES = {
  "upset": {
    "geneset_ids": [
      167180,
      378899,
      164706,
      379321,
      233535
    ],
    "gene_counts": {
      "167180": 74,
      "378899": 162,
      "164706": 84,
      "379321": 59,
      "233535": 199
    },
    "intersections": [
      {
        "geneset_ids": [
          "233535"
        ],
        "size": 159
      },
      {
        "geneset_ids": [
          "378899"
        ],
        "size": 124
      },
      {
        "geneset_ids": [
          "164706",
          "167180"
        ],
        "size": 29
      },
      {
        "geneset_ids": [
          "164706"
        ],
        "size": 28
      },
      {
        "geneset_ids": [
          "379321"
        ],
        "size": 23
      },
      {
        "geneset_ids": [
          "167180"
        ],
        "size": 19
      },
      {
        "geneset_ids": [
          "233535",
          "378899"
        ],
        "size": 11
      },
      {
        "geneset_ids": [
          "233535",
          "379321"
        ],
        "size": 9
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "378899"
        ],
        "size": 6
      },
      {
        "geneset_ids": [
          "167180",
          "379321"
        ],
        "size": 5
      },
      {
        "geneset_ids": [
          "378899",
          "379321"
        ],
        "size": 5
      },
      {
        "geneset_ids": [
          "164706",
          "378899"
        ],
        "size": 4
      },
      {
        "geneset_ids": [
          "233535",
          "378899",
          "379321"
        ],
        "size": 4
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "379321"
        ],
        "size": 3
      },
      {
        "geneset_ids": [
          "164706",
          "233535"
        ],
        "size": 3
      },
      {
        "geneset_ids": [
          "164706",
          "233535",
          "379321"
        ],
        "size": 3
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "233535"
        ],
        "size": 2
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "233535",
          "378899"
        ],
        "size": 2
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "233535",
          "378899",
          "379321"
        ],
        "size": 2
      },
      {
        "geneset_ids": [
          "167180",
          "233535"
        ],
        "size": 2
      },
      {
        "geneset_ids": [
          "167180",
          "233535",
          "378899",
          "379321"
        ],
        "size": 2
      },
      {
        "geneset_ids": [
          "164706",
          "167180",
          "378899",
          "379321"
        ],
        "size": 1
      },
      {
        "geneset_ids": [
          "164706",
          "379321"
        ],
        "size": 1
      },
      {
        "geneset_ids": [
          "167180",
          "378899",
          "379321"
        ],
        "size": 1
      }
    ]
  },
  "hypergeometric": {
    "geneset_ids": [
      "167180",
      "378899",
      "164706",
      "379321",
      "233535"
    ],
    "results": [
      {
        "i": 0,
        "j": 1,
        "odds_ratio": 0.35630630630630633,
        "upper_tail": 0.0004285680234713837,
        "lower_tail": 0.00038233100304378123,
        "two_tailed": 0.0005557544079257043,
        "hypergeometric": 0.9996176689969563
      },
      {
        "i": 0,
        "j": 2,
        "odds_ratio": 13.328912466843502,
        "upper_tail": 1.2393377436997773e-19,
        "lower_tail": 1.149224993285483e-19,
        "two_tailed": 1.2393377436997773e-19,
        "hypergeometric": 1.0
      },
      {
        "i": 0,
        "j": 3,
        "odds_ratio": 1.7059259259259258,
        "upper_tail": 0.08251885566848147,
        "lower_tail": 0.08953187175665951,
        "two_tailed": 0.13085541049704588,
        "hypergeometric": 0.9174811443315185
      },
      {
        "i": 0,
        "j": 4,
        "odds_ratio": 0.1529431216931217,
        "upper_tail": 1.1446283069571215e-09,
        "lower_tail": 7.77177798559724e-10,
        "two_tailed": 1.2586577597746332e-09,
        "hypergeometric": 0.9999999992228222
      },
      {
        "i": 1,
        "j": 2,
        "odds_ratio": 0.32091097308488614,
        "upper_tail": 6.607301695113043e-05,
        "lower_tail": 4.8541873493963096e-05,
        "two_tailed": 8.076498936246195e-05,
        "hypergeometric": 0.999951458126506
      },
      {
        "i": 1,
        "j": 3,
        "odds_ratio": 0.5612244897959183,
        "upper_tail": 0.05917710186017846,
        "lower_tail": 0.042674431454617065,
        "two_tailed": 0.08054088036416644,
        "hypergeometric": 0.957325568545383
      },
      {
        "i": 1,
        "j": 4,
        "odds_ratio": 0.09036576619650968,
        "upper_tail": 9.690880439475889e-26,
        "lower_tail": 8.718199832121422e-26,
        "two_tailed": 1.0463678931169255e-25,
        "hypergeometric": 1.0
      },
      {
        "i": 2,
        "j": 3,
        "odds_ratio": 0.8687258687258688,
        "upper_tail": 0.5632513152817847,
        "lower_tail": 0.43087923530768846,
        "two_tailed": 0.8581158429161995,
        "hypergeometric": 0.5691207646923115
      },
      {
        "i": 2,
        "j": 4,
        "odds_ratio": 0.15775401069518716,
        "upper_tail": 1.5078067404209006e-10,
        "lower_tail": 1.084417181854388e-10,
        "two_tailed": 1.6725499901217045e-10,
        "hypergeometric": 0.9999999998915583
      },
      {
        "i": 3,
        "j": 4,
        "odds_ratio": 0.6016330038676407,
        "upper_tail": 0.06343416834537266,
        "lower_tail": 0.05327118230610256,
        "two_tailed": 0.09203902136369177,
        "hypergeometric": 0.9467288176938975
      }
    ]
  },
  "jaccard_similarity": {
    "geneset_ids": [
      "167180",
      "378899",
      "164706",
      "379321",
      "233535"
    ],
    "include_homology": false,
    "p_value_threshold": 0.05,
    "results": [
      {
        "i": 0,
        "j": 1,
        "jaccard": 0.06306306306306306,
        "p_value": 0.0,
        "intersection": 14,
        "only_i": 60,
        "only_j": 148
      },
      {
        "i": 0,
        "j": 2,
        "jaccard": 0.39823008849557523,
        "p_value": 0.001996007984031936,
        "intersection": 45,
        "only_i": 29,
        "only_j": 39
      },
      {
        "i": 0,
        "j": 3,
        "jaccard": 0.11764705882352941,
        "p_value": 0.0,
        "intersection": 14,
        "only_i": 60,
        "only_j": 45
      },
      {
        "i": 0,
        "j": 4,
        "jaccard": 0.03802281368821293,
        "p_value": 0.0,
        "intersection": 10,
        "only_i": 64,
        "only_j": 189
      },
      {
        "i": 1,
        "j": 2,
        "jaccard": 0.06493506493506493,
        "p_value": 0.0,
        "intersection": 15,
        "only_i": 147,
        "only_j": 69
      },
      {
        "i": 1,
        "j": 3,
        "jaccard": 0.07281553398058252,
        "p_value": 0.0,
        "intersection": 15,
        "only_i": 147,
        "only_j": 44
      },
      {
        "i": 1,
        "j": 4,
        "jaccard": 0.061764705882352944,
        "p_value": 0.0,
        "intersection": 21,
        "only_i": 141,
        "only_j": 178
      },
      {
        "i": 2,
        "j": 3,
        "jaccard": 0.07518796992481203,
        "p_value": 0.0,
        "intersection": 10,
        "only_i": 74,
        "only_j": 49
      },
      {
        "i": 2,
        "j": 4,
        "jaccard": 0.04428044280442804,
        "p_value": 0.0,
        "intersection": 12,
        "only_i": 72,
        "only_j": 187
      },
      {
        "i": 3,
        "j": 4,
        "jaccard": 0.08403361344537816,
        "p_value": 0.0,
        "intersection": 20,
        "only_i": 39,
        "only_j": 179
      }
    ]
  },
  "jaccard_similarity_pair": {
    "geneset_ids": [
      "400405",
      "14923"
    ],
    "include_homology": false,
    "p_value_threshold": 0.05,
    "results": [
      {
        "i": 0,
        "j": 1,
        "jaccard": 0.1836734693877551,
        "p_value": 0.001996007984031936,
        "intersection": 9,
        "only_i": 22,
        "only_j": 18
      }
    ]
  },
  "jaccard_clustering": {
    "geneset_ids": [
      "167180",
      "378899",
      "164706",
      "379321",
      "233535"
    ],
    "method": "average",
    "tree": {
      "geneset_id": null,
      "distance": 0.9429746060449069,
      "children": [
        {
          "geneset_id": "233535",
          "distance": null,
          "children": []
        },
        {
          "geneset_id": null,
          "distance": 0.9330621126737633,
          "children": [
            {
              "geneset_id": "378899",
              "distance": null,
              "children": []
            },
            {
              "geneset_id": null,
              "distance": 0.9035824856258292,
              "children": [
                {
                  "geneset_id": "379321",
                  "distance": null,
                  "children": []
                },
                {
                  "geneset_id": null,
                  "distance": 0.6017699115044248,
                  "children": [
                    {
                      "geneset_id": "167180",
                      "distance": null,
                      "children": []
                    },
                    {
                      "geneset_id": "164706",
                      "distance": null,
                      "children": []
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  },
  "dbscan": {
    "ran": true,
    "clusters": [
      [
        "Gnaz",
        "Slc6a4",
        "Cnr1",
        "Rgs4",
        "Kcnk2",
        "Hltf",
        "Slc6a2",
        "Hipk2",
        "Tamalin",
        "Taok2",
        "Serpina6",
        "Ppp1r1b"
      ]
    ],
    "num_genes": 448,
    "num_genesets": 5
  },
  "boolean_algebra": {
    "relation": "Intersection",
    "at_least": 2,
    "num_genesets": 5,
    "num_species": 1,
    "geneset_ids": [
      164706,
      167180,
      378899,
      379321,
      233535
    ],
    "species_ids": [
      1
    ],
    "bool_results": {
      "5159": [
        [
          5159,
          "Dlg4",
          1,
          164706
        ],
        [
          5159,
          "Mm.27256",
          1,
          164706
        ],
        [
          5159,
          "Dlg4",
          1,
          167180
        ],
        [
          5159,
          "Mm.27256",
          1,
          167180
        ]
      ],
      "1510": [
        [
          1510,
          "Mm.30424",
          1,
          233535
        ],
        [
          1510,
          "Ptger3",
          1,
          233535
        ],
        [
          1510,
          "Ptger3",
          1,
          378899
        ],
        [
          1510,
          "Mm.30424",
          1,
          378899
        ]
      ],
      "18210": [
        [
          18210,
          "Hrh4",
          1,
          378899
        ],
        [
          18210,
          "Mm.207073",
          1,
          378899
        ],
        [
          18210,
          "Mm.207073",
          1,
          379321
        ],
        [
          18210,
          "Hrh4",
          1,
          379321
        ]
      ],
      "27360": [
        [
          27360,
          "Mm.334198",
          1,
          233535
        ],
        [
          27360,
          "Ppp1ccb",
          1,
          233535
        ]
      ],
      "208": [
        [
          208,
          "Mm.222329",
          1,
          233535
        ],
        [
          208,
          "Camk4",
          1,
          233535
        ]
      ],
      "20078": [
        [
          20078,
          "Mm.66952",
          1,
          233535
        ],
        [
          20078,
          "Adcy10",
          1,
          233535
        ]
      ]
    },
    "circle_groups": {
      "5159": [
        164706,
        164706,
        167180,
        167180
      ],
      "1510": [
        233535,
        233535,
        378899,
        378899
      ],
      "18210": [
        378899,
        378899,
        379321,
        379321
      ],
      "27360": [
        233535,
        233535
      ],
      "208": [
        233535,
        233535
      ],
      "20078": [
        233535,
        233535
      ]
    },
    "intersect_results": {
      "1": {
        "27360": [
          [
            27360,
            "Mm.334198",
            1,
            233535
          ]
        ],
        "208": [
          [
            208,
            "Mm.222329",
            1,
            233535
          ]
        ],
        "20078": [
          [
            20078,
            "Mm.66952",
            1,
            233535
          ]
        ]
      },
      "2": {
        "5159": [
          [
            5159,
            "Dlg4",
            1,
            164706
          ],
          [
            5159,
            "Dlg4",
            1,
            167180
          ]
        ],
        "1510": [
          [
            1510,
            "Mm.30424",
            1,
            233535
          ],
          [
            1510,
            "Ptger3",
            1,
            378899
          ]
        ],
        "18210": [
          [
            18210,
            "Hrh4",
            1,
            378899
          ],
          [
            18210,
            "Mm.207073",
            1,
            379321
          ]
        ]
      },
      "4": {},
      "3": {},
      "5": {}
    },
    "bool_except": null
  },
  "boolean_algebra_full_counts": {
    "genes": 448,
    "in_two_or_more": 95,
    "intersect_keys": 447
  },
  "mset": {
    "intersect_genes": [
      "Serpina6",
      "Cacna1b",
      "Plat",
      "Cnr1",
      "Cd81"
    ],
    "mset_data": {
      "Alternative": "Greater",
      "List 1 / Universe": "74",
      "List 1 Size": "74",
      "List 1/2 Intersect": "45",
      "List 2 / Universe": "84",
      "List 2 Size": "84",
      "Method": "Over",
      "Num Trials": "1000",
      "P-Value": "0.000000",
      "Trials gt intersect": "0",
      "Universe Size": "66866"
    },
    "mset_hist": {
      "0": "0.911",
      "1": "0.084",
      "2": "0.005"
    }
  },
  "phenome_map": {
    "bootstrap_applied": false,
    "cut_depth": 0,
    "nodes": [
      {
        "children": [
          {
            "score": 0.5,
            "target": 4
          },
          {
            "score": 0.6666666666666666,
            "target": 7
          },
          {
            "score": 0.4,
            "target": 10
          },
          {
            "score": 0.5,
            "target": 16
          }
        ],
        "depth": 0,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1"
        ],
        "genesets": [
          "164706",
          "167180",
          "233535",
          "378899",
          "379321"
        ],
        "id": 5,
        "parents": []
      },
      {
        "children": [
          {
            "score": 0.6666666666666666,
            "target": 3
          },
          {
            "score": 0.36363636363636365,
            "target": 6
          },
          {
            "score": 0.6666666666666666,
            "target": 15
          }
        ],
        "depth": 1,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Adora2a",
          "Npy1r"
        ],
        "genesets": [
          "164706",
          "167180",
          "233535",
          "378899"
        ],
        "id": 4,
        "parents": [
          5
        ]
      },
      {
        "children": [
          {
            "score": 0.2727272727272727,
            "target": 6
          },
          {
            "score": 0.5,
            "target": 8
          },
          {
            "score": 0.5,
            "target": 18
          }
        ],
        "depth": 1,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Grm5"
        ],
        "genesets": [
          "164706",
          "167180",
          "378899",
          "379321"
        ],
        "id": 7,
        "parents": [
          5
        ]
      },
      {
        "children": [
          {
            "score": 0.6666666666666666,
            "target": 15
          },
          {
            "score": 0.6666666666666666,
            "target": 18
          },
          {
            "score": 0.5,
            "target": 22
          }
        ],
        "depth": 1,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Chrm2",
          "Gabbr1"
        ],
        "genesets": [
          "167180",
          "233535",
          "378899",
          "379321"
        ],
        "id": 16,
        "parents": [
          5
        ]
      },
      {
        "children": [
          {
            "score": 0.13333333333333333,
            "target": 2
          },
          {
            "score": 0.5,
            "target": 9
          },
          {
            "score": 0.6,
            "target": 14
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Ppp1r1b",
          "Adora2a",
          "Npy1r",
          "Htr6"
        ],
        "genesets": [
          "164706",
          "167180",
          "233535"
        ],
        "id": 3,
        "parents": [
          4
        ]
      },
      {
        "children": [
          {
            "score": 0.24444444444444444,
            "target": 2
          },
          {
            "score": 0.7333333333333333,
            "target": 11
          },
          {
            "score": 0.7857142857142857,
            "target": 17
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Adora2a",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Grm5"
        ],
        "genesets": [
          "164706",
          "167180",
          "378899"
        ],
        "id": 6,
        "parents": [
          4,
          7
        ]
      },
      {
        "children": [
          {
            "score": 0.13333333333333333,
            "target": 2
          },
          {
            "score": 0.6,
            "target": 12
          },
          {
            "score": 0.42857142857142855,
            "target": 19
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Drd2",
          "Drd3",
          "Drd4",
          "Drd1",
          "Grm5"
        ],
        "genesets": [
          "164706",
          "167180",
          "379321"
        ],
        "id": 8,
        "parents": [
          7
        ]
      },
      {
        "children": [
          {
            "score": 0.4166666666666667,
            "target": 9
          },
          {
            "score": 0.5,
            "target": 12
          },
          {
            "score": 0.25,
            "target": 23
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd5",
          "Drd1",
          "Gria1",
          "Grin1"
        ],
        "genesets": [
          "164706",
          "233535",
          "379321"
        ],
        "id": 10,
        "parents": [
          5
        ]
      },
      {
        "children": [
          {
            "score": 0.6,
            "target": 14
          },
          {
            "score": 0.42857142857142855,
            "target": 17
          },
          {
            "score": 0.2857142857142857,
            "target": 21
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Adora2a",
          "Npy1r",
          "Chrm2",
          "Gabbr1"
        ],
        "genesets": [
          "167180",
          "233535",
          "378899"
        ],
        "id": 15,
        "parents": [
          4,
          16
        ]
      },
      {
        "children": [
          {
            "score": 0.42857142857142855,
            "target": 17
          },
          {
            "score": 0.42857142857142855,
            "target": 19
          },
          {
            "score": 0.4,
            "target": 25
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Grm5",
          "Chrm2",
          "Gabbr1",
          "Htr2c"
        ],
        "genesets": [
          "167180",
          "378899",
          "379321"
        ],
        "id": 18,
        "parents": [
          7,
          16
        ]
      },
      {
        "children": [
          {
            "score": 0.38095238095238093,
            "target": 21
          },
          {
            "score": 0.4,
            "target": 23
          },
          {
            "score": 0.5333333333333333,
            "target": 25
          }
        ],
        "depth": 2,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Chrm2",
          "Gabbr1",
          "Adrb1",
          "Htr1a",
          "Htr1b",
          "Htr1d"
        ],
        "genesets": [
          "233535",
          "378899",
          "379321"
        ],
        "id": 22,
        "parents": [
          16
        ]
      },
      {
        "children": [
          {
            "score": 0.5357142857142857,
            "target": 1
          },
          {
            "score": 0.6081081081081081,
            "target": 13
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Cacna1b",
          "Drd2",
          "Drd3",
          "Drd4",
          "Tacr1",
          "Drd1",
          "Slc18a2",
          "Rgs4",
          "Chrm5",
          "Cd81",
          "Lrrk2",
          "Cyfip2",
          "Slc29a1",
          "Calca",
          "Unc79",
          "Slc17a8",
          "Serpina6",
          "Gnaz",
          "Slc6a2",
          "Hipk2",
          "Tamalin",
          "Taok2",
          "Rps6ka5",
          "Ppp1r1b",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Prkcg",
          "Plat",
          "Adora2a",
          "Cckbr",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Aqp4",
          "Htr6",
          "Dlg4",
          "Wfs1",
          "Trpv1",
          "Grm5",
          "Apba1",
          "Gprasp1",
          "Pdlim5"
        ],
        "genesets": [
          "164706",
          "167180"
        ],
        "id": 2,
        "parents": [
          3,
          6,
          8
        ]
      },
      {
        "children": [
          {
            "score": 0.14285714285714285,
            "target": 1
          },
          {
            "score": 0.06030150753768844,
            "target": 20
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Atp1a1",
          "Atp1a3",
          "Drd2",
          "Drd5",
          "Drd1",
          "Creb1",
          "Ppp1r1b",
          "Gria1",
          "Grin1",
          "Adora2a",
          "Npy1r",
          "Htr6"
        ],
        "genesets": [
          "164706",
          "233535"
        ],
        "id": 9,
        "parents": [
          3,
          10
        ]
      },
      {
        "children": [
          {
            "score": 0.17857142857142858,
            "target": 1
          },
          {
            "score": 0.09259259259259259,
            "target": 24
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Taar1",
          "Crhr1",
          "Oprd1",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Adora2a",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Grm5",
          "Prlhr"
        ],
        "genesets": [
          "164706",
          "378899"
        ],
        "id": 11,
        "parents": [
          6
        ]
      },
      {
        "children": [
          {
            "score": 0.11904761904761904,
            "target": 1
          },
          {
            "score": 0.1694915254237288,
            "target": 26
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Drd2",
          "Drd3",
          "Drd4",
          "Drd5",
          "Drd1",
          "Chrnb2",
          "Gria1",
          "Grin1",
          "Grm5"
        ],
        "genesets": [
          "164706",
          "379321"
        ],
        "id": 12,
        "parents": [
          8,
          10
        ]
      },
      {
        "children": [
          {
            "score": 0.13513513513513514,
            "target": 13
          },
          {
            "score": 0.05025125628140704,
            "target": 20
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Ppp1r1b",
          "Adora2a",
          "Npy1r",
          "Htr6",
          "Chrm2",
          "Adcy5",
          "Gabbr1",
          "Gabbr2"
        ],
        "genesets": [
          "167180",
          "233535"
        ],
        "id": 14,
        "parents": [
          3,
          15
        ]
      },
      {
        "children": [
          {
            "score": 0.1891891891891892,
            "target": 13
          },
          {
            "score": 0.08641975308641975,
            "target": 24
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Adora2a",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Grm5",
          "Chrm2",
          "Gabbr1",
          "Htr2c"
        ],
        "genesets": [
          "167180",
          "378899"
        ],
        "id": 17,
        "parents": [
          6,
          15,
          18
        ]
      },
      {
        "children": [
          {
            "score": 0.1891891891891892,
            "target": 13
          },
          {
            "score": 0.23728813559322035,
            "target": 26
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Drd2",
          "Drd3",
          "Drd4",
          "Drd1",
          "Grm5",
          "Chrm2",
          "Gabra1",
          "Gabra2",
          "Gabrb3",
          "Gabrd",
          "Gabrg2",
          "Gabbr1",
          "Htr2c"
        ],
        "genesets": [
          "167180",
          "379321"
        ],
        "id": 19,
        "parents": [
          8,
          18
        ]
      },
      {
        "children": [
          {
            "score": 0.10552763819095477,
            "target": 20
          },
          {
            "score": 0.12962962962962962,
            "target": 24
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Adora2a",
          "Npy1r",
          "Chrm2",
          "Gabbr1",
          "Ptger3",
          "Sstr1",
          "Sstr2",
          "Tshr",
          "Ffar2",
          "F2r",
          "Adcyap1r1",
          "Adrb1",
          "Adrb2",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Ednra",
          "Hcar2",
          "Hcar1"
        ],
        "genesets": [
          "233535",
          "378899"
        ],
        "id": 21,
        "parents": [
          15,
          22
        ]
      },
      {
        "children": [
          {
            "score": 0.10050251256281408,
            "target": 20
          },
          {
            "score": 0.3389830508474576,
            "target": 26
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd5",
          "Drd1",
          "Gria1",
          "Grin1",
          "Chrm2",
          "Gabbr1",
          "Chrm1",
          "Adrb1",
          "Gria2",
          "Gria3",
          "Gria4",
          "Grin2a",
          "Grin2b",
          "Grin2c",
          "Grin2d",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Grin3a"
        ],
        "genesets": [
          "233535",
          "379321"
        ],
        "id": 23,
        "parents": [
          10,
          22
        ]
      },
      {
        "children": [
          {
            "score": 0.09259259259259259,
            "target": 24
          },
          {
            "score": 0.2542372881355932,
            "target": 26
          }
        ],
        "depth": 3,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Grm5",
          "Chrm2",
          "Gabbr1",
          "Htr2c",
          "Adrb1",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Chrm4",
          "Htr5b",
          "Htr2b",
          "Grm1",
          "Hrh4"
        ],
        "genesets": [
          "378899",
          "379321"
        ],
        "id": 25,
        "parents": [
          18,
          22
        ]
      },
      {
        "children": [],
        "depth": 4,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Atp1a1",
          "Atp1a3",
          "Cacna1b",
          "Drd2",
          "Drd3",
          "Drd4",
          "Drd5",
          "Tacr1",
          "Drd1",
          "Aldh2",
          "Alk",
          "Slc18a2",
          "Rgs4",
          "Chrm5",
          "Lmo4",
          "Cd81",
          "Skap2",
          "Lrrk2",
          "Cyfip2",
          "Slc29a1",
          "Taar1",
          "Calca",
          "Unc79",
          "Slc17a8",
          "Chrnb2",
          "Serpina6",
          "Creb1",
          "Crhr1",
          "Fyn",
          "Gabrb1",
          "Slc6a1",
          "Gnaz",
          "Nos1",
          "Slc6a2",
          "Hipk2",
          "Mpdz",
          "Tamalin",
          "Nacc1",
          "Taok2",
          "Rps6ka5",
          "Sorcs2",
          "Ppp1r1b",
          "Gria1",
          "Grin1",
          "Hdc",
          "Il6",
          "Oprd1",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Prkcg",
          "Plat",
          "Pomc",
          "Prkar2b",
          "Adora2a",
          "Cckbr",
          "Clock",
          "Cnr1",
          "Penk",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Aqp4",
          "Per2",
          "Htr6",
          "Map6",
          "Dlg4",
          "Wfs1",
          "Trpv1",
          "Grk6",
          "Homer1",
          "Homer2",
          "Grm5",
          "Nr4a2",
          "Apba1",
          "Gprasp1",
          "Ppp1r14c",
          "Pdlim5",
          "Prlhr",
          "Dtnbp1",
          "Ppp1r9b",
          "Adgrl3",
          "Ppp1r9a"
        ],
        "genesets": [
          "164706"
        ],
        "id": 1,
        "parents": [
          2,
          9,
          11,
          12
        ]
      },
      {
        "children": [],
        "depth": 4,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Cacna1b",
          "Drd2",
          "Drd3",
          "Drd4",
          "Tacr1",
          "Drd1",
          "Slc18a2",
          "Rgs4",
          "Chrm5",
          "Cd81",
          "Lrrk2",
          "Cyfip2",
          "Slc29a1",
          "Calca",
          "Unc79",
          "Slc17a8",
          "Serpina6",
          "Gnaz",
          "Slc6a2",
          "Hipk2",
          "Tamalin",
          "Taok2",
          "Rps6ka5",
          "Ppp1r1b",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Prkcg",
          "Plat",
          "Adora2a",
          "Cckbr",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Aqp4",
          "Htr6",
          "Dlg4",
          "Wfs1",
          "Trpv1",
          "Grm5",
          "Apba1",
          "Gprasp1",
          "Pdlim5",
          "Cacna2d1",
          "Chrm2",
          "Cacnb4",
          "Upp1",
          "Cacna1g",
          "Gabra1",
          "Gabra2",
          "Gabra4",
          "Gabrb3",
          "Gabrd",
          "Gabrg2",
          "Slc6a4",
          "Adcy5",
          "Kcnk2",
          "Hltf",
          "S100a10",
          "Gabbr1",
          "Gabbr2",
          "Dgkb",
          "Dao",
          "Htr2c",
          "Kit",
          "Nr1i2",
          "Mgll",
          "Prkn",
          "Mchr1",
          "Nr1d2",
          "Plcl1",
          "A4galt"
        ],
        "genesets": [
          "167180"
        ],
        "id": 13,
        "parents": [
          2,
          14,
          17,
          19
        ]
      },
      {
        "children": [],
        "depth": 4,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Atp1a1",
          "Atp1a3",
          "Drd2",
          "Drd5",
          "Drd1",
          "Creb1",
          "Ppp1r1b",
          "Gria1",
          "Grin1",
          "Adora2a",
          "Npy1r",
          "Htr6",
          "Chrm2",
          "Adcy5",
          "Gabbr1",
          "Gabbr2",
          "Akt1",
          "Amh",
          "Atp1a2",
          "Atp1b1",
          "Atp1b2",
          "Atp2a2",
          "Atp2b4",
          "Braf",
          "Calm1",
          "Camk2a",
          "Camk2b",
          "Camk4",
          "Camk2g",
          "Cacna1d",
          "Cacna1s",
          "Chrm1",
          "Lipe",
          "Ptger2",
          "Ptger3",
          "Rac1",
          "Rac2",
          "Raf1",
          "Rap1a",
          "Rras",
          "Sstr1",
          "Sstr2",
          "Tnni3",
          "Tshr",
          "Vav1",
          "Vav2",
          "Cacna1c",
          "Calm3",
          "Calm2",
          "Rela",
          "Tiam1",
          "Atp2b1",
          "Akt2",
          "Atp2b2",
          "Ptch1",
          "Atp1b3",
          "Rock2",
          "Rock1",
          "Sstr5",
          "Rap1b",
          "Rhoa",
          "Camk2d",
          "Akt3",
          "Atp2b3",
          "Atp1a4",
          "Cacna1f",
          "Vav3",
          "Rras2",
          "Atp1b4",
          "Calml3",
          "Rapgef4",
          "Calm4",
          "Sucnr1",
          "Rac3",
          "Ffar2",
          "Rapgef3",
          "Calm5",
          "Adcy6",
          "Cftr",
          "Fos",
          "Gli1",
          "Gli3",
          "Gnai1",
          "Gnai2",
          "Gnai3",
          "Gnas",
          "Nfkb1",
          "Sox9",
          "Glp1r",
          "Adcy4",
          "Adcy3",
          "Adcy2",
          "Adcy1",
          "Ryr2",
          "Creb3",
          "F2r",
          "Slc9a1",
          "Nfatc1",
          "Adcy7",
          "Nfkbia",
          "Adcyap1r1",
          "Adcy9",
          "Oxtr",
          "Bad",
          "Crebbp",
          "Fxyd2",
          "Acox1",
          "Pak1",
          "Adcy8",
          "Hhip",
          "Creb3l1",
          "Gipr",
          "Fxyd1",
          "4930544G11Rik",
          "Creb3l4",
          "Acox3",
          "Myl9",
          "Creb3l3",
          "Creb3l2",
          "Abcc4",
          "Creb5",
          "Adcy10",
          "Gpr119",
          "Adrb1",
          "Adrb2",
          "Bdnf",
          "Cnga1",
          "Fshb",
          "Fshr",
          "Gria2",
          "Gria3",
          "Gria4",
          "Grin2a",
          "Grin2b",
          "Grin2c",
          "Grin2d",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Jun",
          "Mc2r",
          "Npr1",
          "Npy",
          "Pik3r1",
          "Prkaca",
          "Prkacb",
          "Pln",
          "Adora1",
          "Pde4d",
          "Pde4c",
          "Pde4b",
          "Pde4a",
          "Htr1f",
          "Ppp1ca",
          "Ppara",
          "Ppp1cb",
          "Ppp1cc",
          "Ednra",
          "Vipr2",
          "Cnga2",
          "Htr4",
          "Pik3r3",
          "Pld1",
          "Pld2",
          "Pik3cd",
          "Pik3r2",
          "Pik3ca",
          "Ep300",
          "Hcn4",
          "Hcn2",
          "Ppp1r12a",
          "Prkx",
          "Afdn",
          "Pde3b",
          "Cnga3",
          "Mapk1",
          "Mapk3",
          "Mapk8",
          "Mapk9",
          "Mapk10",
          "Map2k1",
          "Map2k2",
          "Cngb3",
          "Pik3cg",
          "Pde3a",
          "Plce1",
          "Pik3cb",
          "Orai1",
          "Ghrl",
          "Grin3a",
          "Hcar2",
          "Arap3",
          "Grin3b",
          "Hcar1",
          "Ghsr",
          "Pik3r5",
          "Cnga4",
          "Cngb1",
          "Ppp1ccb"
        ],
        "genesets": [
          "233535"
        ],
        "id": 20,
        "parents": [
          9,
          14,
          21,
          23
        ]
      },
      {
        "children": [],
        "depth": 4,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Drd2",
          "Drd1",
          "Taar1",
          "Crhr1",
          "Oprd1",
          "Oprk1",
          "Oprl1",
          "Oprm1",
          "Adora2a",
          "Cnr1",
          "Adra1b",
          "Npy1r",
          "Adra1d",
          "Grm5",
          "Prlhr",
          "Chrm2",
          "Gabbr1",
          "Htr2c",
          "Ptger3",
          "Sstr1",
          "Sstr2",
          "Tshr",
          "Ffar2",
          "F2r",
          "Adcyap1r1",
          "Adrb1",
          "Adrb2",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Ednra",
          "Hcar2",
          "Hcar1",
          "Chrm4",
          "Pth1r",
          "Tbxa2r",
          "Calcr",
          "Ptgdr",
          "Ptger4",
          "Cxcr2",
          "Lpar1",
          "Ltb4r1",
          "Ptgdr2",
          "Cx3cr1",
          "Ltb4r2",
          "Lpar4",
          "Calcrl",
          "Cxcr6",
          "Tm2d1",
          "Ffar4",
          "Slc22a22",
          "Ffar1",
          "Taar4",
          "Taar5",
          "Ffar3",
          "Taar3",
          "Taar7f",
          "Lhcgr",
          "Ntsr1",
          "F2rl1",
          "Mtnr1a",
          "Ntsr2",
          "Crhr2",
          "S1pr1",
          "Galr1",
          "Crcp",
          "Inpp5k",
          "S1pr4",
          "S1pr3",
          "Nmur1",
          "Ackr2",
          "Cysltr2",
          "P2ry12",
          "Cysltr1",
          "P2ry4",
          "Tas1r3",
          "S1pr5",
          "Sctr",
          "Nmur2",
          "Rxfp3",
          "P2ry6",
          "Gpr139",
          "Mrgpra1",
          "Mrgpra4",
          "Mrgprx2",
          "Adra2a",
          "Adra2b",
          "Adra2c",
          "Agtr1a",
          "Agtr2",
          "Ghrhr",
          "Grpr",
          "Htr5b",
          "Mas1",
          "Mc3r",
          "Adora2b",
          "Mc1r",
          "Mc4r",
          "Gcgr",
          "Ppard",
          "Ednrb",
          "Ccr7",
          "Ccr3",
          "Ccr1",
          "Adra1a",
          "Adora3",
          "Npy4r",
          "Ccr2",
          "Ccr5",
          "Fpr1",
          "Ccr4",
          "Npy5r",
          "Npy2r",
          "Htr2b",
          "Ccr10",
          "Npy6r",
          "Ccr8",
          "Adgrv1",
          "Fpr-rs4",
          "Fpr-rs3",
          "Fpr2",
          "Ccr6",
          "Agtrap",
          "Adgrg1",
          "Ccr9",
          "Grm1",
          "Grm2",
          "Grm3",
          "Grm4",
          "Grm6",
          "Grm7",
          "Grm8",
          "Opn4",
          "Gpr31b",
          "Gpr173",
          "Gpr39",
          "Gpr15",
          "Adgrf1",
          "Prokr1",
          "Kiss1r",
          "Gpr6",
          "Prokr2",
          "Gprc6a",
          "Hrh4",
          "Gpr75",
          "Gpr4",
          "Gpr157",
          "Fpr-rs6",
          "Fpr-rs7",
          "Opn5",
          "Vmn2r26",
          "Hcrtr2",
          "Vmn2r81",
          "Gpr161",
          "Gpr174",
          "Gpr176",
          "Vmn2r65",
          "Vmn2r120",
          "Vmn2r83",
          "Vmn2r1",
          "Vmn2r82",
          "Vmn2r116"
        ],
        "genesets": [
          "378899"
        ],
        "id": 24,
        "parents": [
          11,
          17,
          21,
          25
        ]
      },
      {
        "children": [],
        "depth": 4,
        "displayed": true,
        "emphasize": true,
        "genes": [
          "Chrna4",
          "Drd2",
          "Drd3",
          "Drd4",
          "Drd5",
          "Drd1",
          "Chrnb2",
          "Gria1",
          "Grin1",
          "Grm5",
          "Chrm2",
          "Gabra1",
          "Gabra2",
          "Gabrb3",
          "Gabrd",
          "Gabrg2",
          "Gabbr1",
          "Htr2c",
          "Chrm1",
          "Adrb1",
          "Gria2",
          "Gria3",
          "Gria4",
          "Grin2a",
          "Grin2b",
          "Grin2c",
          "Grin2d",
          "Htr1a",
          "Htr1b",
          "Htr1d",
          "Grin3a",
          "Chrm4",
          "Htr5b",
          "Htr2b",
          "Grm1",
          "Hrh4",
          "Chrna1",
          "Chrna3",
          "Chrna10",
          "Chrnb1",
          "Chrnb4",
          "Chrnd",
          "Chrne",
          "Chrng",
          "Gabra3",
          "Gabra6",
          "Gabrb2",
          "Gabrg3",
          "Gabrr1",
          "Glra1",
          "Glra2",
          "Glrb",
          "Chrna7",
          "Chrna6",
          "Chrna9",
          "Grik1",
          "Grik2",
          "Grik5",
          "Htr3b"
        ],
        "genesets": [
          "379321"
        ],
        "id": 26,
        "parents": [
          12,
          19,
          23,
          25
        ]
      }
    ],
    "notes": [],
    "num_genes": 448,
    "num_genesets": 5
  },
  "combine": {
    "geneset_ids": [
      167180,
      378899,
      164706,
      379321,
      233535
    ],
    "include_homology": true,
    "matrix": {
      "23": {
        "0": "Mm.4583",
        "379321": 1
      },
      "25": {
        "0": "Mm.63569",
        "379321": 1
      },
      "26": {
        "0": "Mm.252369",
        "379321": 1,
        "164706": 1,
        "167180": 1
      },
      "28": {
        "0": "Mm.86425",
        "379321": 1
      },
      "29": {
        "0": "Mm.35088",
        "164706": 1,
        "379321": 1
      },
      "30": {
        "0": "Chrnb4",
        "379321": 1
      },
      "31": {
        "0": "Mm.2811",
        "379321": 1
      },
      "32": {
        "0": "Mm.4980",
        "379321": 1
      }
    },
    "gslabels": {
      "164706": "abnormal behavioral response to addictive substance (MP)",
      "167180": "impaired behavioral response to xenobiotic (MP)",
      "233535": "cAMP signaling pathway",
      "378899": "GO:0004930",
      "379321": "GO:0030594"
    },
    "gsnames": {
      "164706": "MP:0009748 abnormal behavioral response to addictive substance",
      "167180": "MP:0009747 impaired behavioral response to xenobiotic",
      "233535": "KEGG Geneset - \"cAMP signaling pathway\" pathway genes",
      "378899": "GO:0004930 G protein-coupled receptor activity",
      "379321": "GO:0030594 neurotransmitter receptor activity"
    }
  }
};
