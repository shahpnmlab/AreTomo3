#include "CMcAreTomoInc.h"
#include "MotionCor/CMotionCorInc.h"
#include "AreTomo/CAreTomoInc.h"
#include "DataUtil/CDataUtilInc.h"
#include <Util/Util_Time.h>
#include <cuda.h>
#include <cuda_runtime.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>

using namespace McAreTomo;
namespace MD = McAreTomo::DataUtil;
namespace MM = McAreTomo::MotionCor;

static MD::CStackFolder* s_pStackFolder = 0L;

CMcAreTomoMain::CMcAreTomoMain(void)
{
	CInput* pInput = CInput::GetInstance();
	int iNumGpus = pInput->m_iNumGpus;
	//-----------------
	MD::CDuInstances::CreateInstances(iNumGpus);
	MotionCor::CMcInstances::CreateInstances(iNumGpus);
	AreTomo::CAtInstances::CreateInstances(iNumGpus);
	//-----------------
	CProcessThread::CreateInstances(iNumGpus);
}

CMcAreTomoMain::~CMcAreTomoMain(void)
{
	CProcessThread::DeleteInstances();
	MD::CDuInstances::DeleteInstances();
	MotionCor::CMcInstances::DeleteInstances();
	AreTomo::CAtInstances::DeleteInstances();
}

bool CMcAreTomoMain::DoIt(void)
{
	//---------------------------------------------------------
	// 1) Load MdocDone.txt from the output folder if there 
	// is one. 2) This is used for resuming processing without
	// reppcessing those that have been processed.
	//--------------------------------------------------
	MD::CReadMdocDone* pReadMdocDone = MD::CReadMdocDone::GetInstance();
	pReadMdocDone->DoIt();
	//---------------------------------------------------------
	// 1) If -Resume 1 and -Cmd 0 are both specified,
	// CStackFolder checks a mdoc file name is in the list of 
	// processed mdoc files. If yes, this mdoc will not be 
	// processed.
	//---------------------------------------------------------
	s_pStackFolder = MD::CStackFolder::GetInstance();
	bool bSuccess = s_pStackFolder->ReadFiles();
	if(!bSuccess)
	{	fprintf(stderr, "Error: no input image files "
		   "are found, quit.\n\n");
		return false;
	}
	//--------------------------------------------------
	// Use the first GPU since dark and gain references
	// are allocated in pinned memory.
	//--------------------------------------------------
	CInput* pInput = CInput::GetInstance();
	cudaSetDevice(pInput->m_piGpuIDs[0]);
	//-----------------------------------
	// load gain and/or dark references.
	//-----------------------------------
	MM::CMotionCorMain::LoadRefs();	
	MM::CMotionCorMain::LoadFmIntFile();
	//--------------------------------------------------------
	// wait a new movie for 10 minutes and quit if not found.
	//--------------------------------------------------------
	bool bExit = false;
	while(true)
	{	int iQueueSize = s_pStackFolder->GetQueueSize();
		if(iQueueSize > 0) 
		{	mProcess();
			s_pStackFolder->WaitForExit(5.0f);
			continue;
		}
		bExit = s_pStackFolder->WaitForExit(1.0f);
		if(bExit) break;
	}
	printf("All mdoc files have been processed, "
	   "waiting processing to finish.\n\n");	
	//-----------------
	while(true)
	{	bExit = CProcessThread::WaitExitAll(1.0f);
		if(bExit) break;
	}
	printf("All threads have finished, program exits.\n\n");
	return true;
}

void CMcAreTomoMain::mProcess(void)
{
	CProcessThread* pProcessThread = CProcessThread::GetFreeThread();
	if(pProcessThread == 0L)
	{	printf("All GPUs are used, wait ......\n\n");
		return;
	}
	int iNthGpu = pProcessThread->m_iNthGpu; 
	//-----------------
	char acMdoc[256] = {'\0'};
	MD::CTsPackage* pTsPackage = MD::CTsPackage::GetInstance(iNthGpu);
	char* pcMdocFile = s_pStackFolder->GetFile(true);
	char* pcMainFile = strrchr(pcMdocFile, '/');
	if(pcMainFile == 0L) strcpy(acMdoc, pcMdocFile);
	else strcpy(acMdoc, &pcMainFile[1]);
	//-----------------
	pTsPackage->SetMdoc(pcMdocFile);
	if(pcMdocFile != 0L) delete[] pcMdocFile;
	//-----------------
	pProcessThread->DoIt();
}

