from models import db, FitnessTestResult
from .serializers import fitness_test_to_dict


def list_results(test_key=None, limit=100):
    q = FitnessTestResult.query
    if test_key:
        q = q.filter_by(test_key=test_key)
    return q.order_by(FitnessTestResult.tested_at.desc()).limit(limit).all()


def create_result(data):
    required = ('test_key', 'category', 'value', 'unit')
    missing = [k for k in required if data.get(k) is None]
    if missing:
        raise ValueError('Missing required fields: ' + ', '.join(missing))
    result = FitnessTestResult(
        test_key=data['test_key'], category=data['category'], value=float(data['value']),
        unit=data['unit'], notes=data.get('notes'), details=data.get('details')
    )
    db.session.add(result)
    db.session.commit()
    return result


def as_dict(result): return fitness_test_to_dict(result)
