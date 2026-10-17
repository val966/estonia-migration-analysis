import sys,unittest,tempfile,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'common'))
from load_worldbank import parse_worldbank
from load_eurostat import decode_jsonstat
from international_common import publish

class InternationalTests(unittest.TestCase):
 def test_worldbank_missing_not_zero(self):
  response=[{'pages':1},[{'indicator':{'id':'A'},'countryiso3code':'EST','date':'2020','value':None}, {'indicator':{'id':'A'},'countryiso3code':'EST','date':'2021','value':7.5}]]
  rows=parse_worldbank(response,'A');self.assertEqual(len(rows),2);self.assertIsNone(rows[0][2]);self.assertEqual(rows[1][2],7.5)
 def test_eurostat_codes_and_flags(self):
  ids=['freq','unit','age','agedef','sex','c_birth','geo','time']
  cats=['A','NR','TOTAL','REACH','M','FOR','EE','2022']
  data={'id':ids,'size':[1]*8,'dimension':{k:{'category':{'index':{v:0}}} for k,v in zip(ids,cats)},'value':{'0':123},'status':{'0':'p'}}
  rows,_=decode_jsonstat(data);self.assertEqual(rows[0],(2022,'EE','FOR','M','TOTAL','A','NR','REACH',123.0,'p'))
 def test_publish_preserves_other_table(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'x.sqlite'
   with sqlite3.connect(db) as c:c.execute('CREATE TABLE rvr03(a TEXT)');c.execute("INSERT INTO rvr03 VALUES('original')")
   publish(db,'worldbank_estonia','CREATE TABLE worldbank_estonia(year INTEGER)',[(2020,)],'INSERT INTO worldbank_estonia VALUES(?)','worldbank','x','https://example.org',{})
   with sqlite3.connect(db) as c:self.assertEqual(c.execute('SELECT a FROM rvr03').fetchone()[0],'original')
if __name__=='__main__':unittest.main()
