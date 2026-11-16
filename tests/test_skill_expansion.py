import unittest
from collections import Counter
from dataclasses import replace
from gateway_pilot.skill_expansion import SkillCatalog, SkillRetriever, CatalogError
from gateway_pilot.skill_expansion.catalog import Relation
from gateway_pilot.skill_expansion.review import existing_v01_edges,candidate_edges_for_review
from gateway_pilot.skill_expansion.retrieval import tokens

class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=SkillCatalog.load()

    def test_full_catalog(self):
        self.assertEqual(len(self.c.skills),120)
        self.assertEqual(len(self.c.relations),206)
        self.assertEqual(len({s.domain for s in self.c.skills.values()}),15)
        self.assertTrue(all(len(self.c.group(domain))==8 for domain in 'ABCDEFGHIJKLMNO'))

    def test_counts_and_nonexecutable(self):
        c=self.c.summary()
        self.assertEqual(c['skills_by_status'],{'EXISTING_V01':8,'PROPOSED':112})
        self.assertEqual(c['relations_by_status'],{'EXISTING_V01':3,'PROPOSED':203})
        self.assertEqual(c['skills_by_priority'],{'P0':36,'P1':50,'P2':34})
        self.assertEqual(c['executable_skills_granted_by_package'],0)
        self.assertTrue(all(s.runtime_status=='NOT_BOUND' for s in self.c.skills.values()))

    def test_v01_edges_match_known_registry(self):
        self.assertEqual({(x['source'],x['target'],x['type']) for x in existing_v01_edges(self.c)},
                         {('SK02','SK01','depends_on'),('SK03','SK01','depends_on'),
                          ('SK04','SK05','composes_with')})
        self.assertEqual(len(candidate_edges_for_review(self.c)),203)

    def test_no_duplicate_edges(self):
        self.assertEqual(len(self.c.relations),len({(r.source,r.target,r.type) for r in self.c.relations}))

    def test_only_hard_dependencies_expand(self):
        self.assertEqual(self.c.hard_dependencies(['SK02']),{'SK01'})
        self.assertEqual(self.c.hard_dependencies(['SK04']),set())
        self.assertEqual(self.c.hard_dependencies(['SK03','SK02']),{'SK01'})

    def test_unapproved_dependencies_not_applied(self):
        # Proposed graph relations never silently become mandatory prerequisites.
        x = self.c.hard_dependencies(['O01'])
        self.assertEqual(x,set())
        proposed = self.c.hard_dependencies(['O01'],preview_proposed=True)
        self.assertTrue(proposed.issubset(set(self.c.skills)))

    def test_invalid_hard_cycle_rejected(self):
        bad=list(self.c.relations)+[Relation('SK01','SK02','depends_on','PROPOSED','bad', '',1.0)]
        with self.assertRaises(CatalogError): SkillCatalog(self.c.skills.values(),bad)

    def test_duplicate_relation_rejected(self):
        with self.assertRaises(CatalogError):
            SkillCatalog(self.c.skills.values(),list(self.c.relations)+[self.c.relations[0]])

    def test_bad_status_rejected(self):
        bad=[replace(self.c.skills['A02'],runtime_status='READY')]
        with self.assertRaises(CatalogError):
            SkillCatalog([*list(s for s in self.c.skills.values() if s.id != 'A02'),*bad], self.c.relations)

    def test_missing_skill_rejected(self):
        with self.assertRaises(CatalogError): self.c.hard_dependencies(['NO_SUCH_SKILL'])

    def test_existing_only_graph_export(self):
        dot=self.c.export_graphviz_dot()
        self.assertIn('"SK02" -> "SK01"',dot)
        self.assertNotIn('"N04" -> "N02"',dot)
        proposal=self.c.export_graphviz_dot(include_proposed=True)
        self.assertIn('"N04" -> "N02"',proposal)
        self.assertIn('style="dashed"',proposal)

    def test_conflict_soft_excluded_from_dependency(self):
        self.assertFalse(self.c.conflicts(['SK02','SK03']))

class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=SkillRetriever(SkillCatalog.load())

    def test_vietnamese_normalization(self):
        self.assertIn('wifi',tokens('Wi-Fi'))
        self.assertEqual(tokens('chẩn đoán'),tokens('chan doan'))

    def test_search_default_does_not_expose_proposed(self):
        result=self.r.search('wifi laptop mạng chậm',limit=12)
        self.assertTrue(result)
        self.assertTrue(all(h.status=='EXISTING_V01' for h in result))

    def test_proposed_search_exposes_candidates(self):
        result=self.r.search('wifi radio channel roaming',limit=30,include_proposed=True)
        self.assertTrue(any(h.status=='PROPOSED' for h in result))
        self.assertTrue(all(h.runtime_status=='NOT_BOUND' for h in result))

    def test_unmatched_query_returns_no_hallucinated_skill(self):
        self.assertEqual(self.r.search('zzzxqqqxy',include_proposed=True),[])

    def test_ppr_non_negative_normalized(self):
        scores=self.r.graph_scores({'SK02':1.0})
        self.assertAlmostEqual(sum(scores.values()),1.0,places=7)
        self.assertTrue(all(v>=0 for v in scores.values()))

    def test_no_seed_returns_no_graph_mass(self):
        self.assertFalse(any(self.r.graph_scores({},include_proposed=True).values()))

    def test_invalid_weight_rejected(self):
        with self.assertRaises(ValueError): self.r.search('wifi',graph_weight=2)

if __name__=='__main__':unittest.main()
