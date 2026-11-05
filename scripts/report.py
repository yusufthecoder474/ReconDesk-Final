import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
import pandas as pd
from core.models import Invoice
rows=[{'invoice':i.number,'amount':float(i.amount),'allocated':float(i.allocated),'outstanding':float(i.outstanding)} for i in Invoice.objects.prefetch_related('allocations')]
df=pd.DataFrame(rows,columns=['invoice','amount','allocated','outstanding'])
print(df.to_string(index=False))
print('Total outstanding:',round(df['outstanding'].sum(),2))
