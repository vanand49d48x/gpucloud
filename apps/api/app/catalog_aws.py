import boto3
import logging
from typing import List, Dict, Any, Optional
from cachetools import TTLCache
from botocore.exceptions import ClientError
from .config import settings

log = logging.getLogger(__name__)

# Cache for instance types and pricing data
_instance_cache = TTLCache(maxsize=100, ttl=settings.CATALOG_CACHE_TTL_SECONDS)
_pricing_cache = TTLCache(maxsize=100, ttl=settings.CATALOG_CACHE_TTL_SECONDS)

def _get_instance_types(region: str) -> List[Dict[str, Any]]:
    """Fetch instance types from AWS with GPU and CPU details."""
    cache_key = f"instances:{region}"
    
    if cache_key in _instance_cache:
        return _instance_cache[cache_key]
    
    try:
        ec2 = boto3.client('ec2', region_name=region)
        response = ec2.describe_instance_types()
        
        instances = []
        for instance in response['InstanceTypes']:
            instance_info = {
                'instance_type': instance['InstanceType'],
                'vcpus': instance['VCpuInfo']['DefaultVCpus'],
                'memory_gb': instance['MemoryInfo']['SizeInMiB'] / 1024,
                'network_performance': instance.get('NetworkInfo', {}).get('NetworkPerformance', 'Unknown'),
                'category': 'CPU'  # Default to CPU
            }
            
            # Check for GPU information
            if 'GpuInfo' in instance:
                gpu_info = instance['GpuInfo']
                instance_info.update({
                    'category': 'GPU',
                    'gpu': {
                        'gpu_count': gpu_info['TotalGpuMemoryInMiB'] // (gpu_info['Gpus'][0]['MemoryInfo']['SizeInMiB'] if gpu_info['Gpus'] else 1),
                        'gpu_model': gpu_info['Gpus'][0]['Name'] if gpu_info['Gpus'] else 'Unknown',
                        'gpu_memory_gb_per_gpu': gpu_info['Gpus'][0]['MemoryInfo']['SizeInMiB'] / 1024 if gpu_info['Gpus'] else 0
                    }
                })
            
            instances.append(instance_info)
        
        _instance_cache[cache_key] = instances
        return instances
        
    except ClientError as e:
        log.error(f"Error fetching instance types for {region}: {e}")
        return []

def _get_pricing(region: str, instance_type: str) -> Optional[float]:
    """Fetch on-demand pricing for an instance type."""
    cache_key = f"pricing:{region}:{instance_type}"
    
    if cache_key in _pricing_cache:
        return _pricing_cache[cache_key]
    
    try:
        pricing = boto3.client('pricing', region_name='us-east-1')  # Pricing API only available in us-east-1
        
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                {'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': region}
            ]
        )
        
        if response['PriceList']:
            # Parse the price from the JSON response
            import json
            price_data = json.loads(response['PriceList'][0])
            
            # Extract the on-demand price
            for term in price_data.get('terms', {}).get('OnDemand', {}).values():
                for price_dimension in term.get('priceDimensions', {}).values():
                    if 'pricePerUnit' in price_dimension and 'USD' in price_dimension['pricePerUnit']:
                        hourly_price = float(price_dimension['pricePerUnit']['USD'])
                        _pricing_cache[cache_key] = hourly_price
                        return hourly_price
        
        return None
        
    except ClientError as e:
        log.error(f"Error fetching pricing for {instance_type} in {region}: {e}")
        return None

def get_catalog(gpu_only: bool = False) -> List[Dict[str, Any]]:
    """Get the complete AWS catalog with pricing and markup."""
    catalog = []
    
    for region in settings.AWS_CATALOG_REGIONS:
        instances = _get_instance_types(region)
        
        for instance in instances:
            # Filter by GPU if requested
            if gpu_only and instance['category'] != 'GPU':
                continue
            
            # Get pricing
            hourly_usd = _get_pricing(region, instance['instance_type'])
            if hourly_usd is None:
                continue  # Skip instances without pricing
            
            # Apply markup
            price_with_markup_usd = hourly_usd * settings.MARKUP_MULTIPLIER
            
            catalog_item = {
                "id": f"aws:{region}:{instance['instance_type']}",
                "provider": "aws",
                "region": region,
                "instance_type": instance['instance_type'],
                "category": instance['category'],
                "gpu": instance.get('gpu'),
                "vcpus": instance['vcpus'],
                "memory_gb": instance['memory_gb'],
                "network_performance": instance['network_performance'],
                "hourly_usd": hourly_usd,
                "price_with_markup_usd": round(price_with_markup_usd, 4)
            }
            
            catalog.append(catalog_item)
    
    # Sort by price
    catalog.sort(key=lambda x: x['price_with_markup_usd'])
    return catalog

def get_instance_by_id(instance_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific instance from the catalog by ID."""
    catalog = get_catalog()
    for item in catalog:
        if item['id'] == instance_id:
            return item
    return None
